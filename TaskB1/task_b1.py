import csv
import logging
import math
import sqlite3
import tempfile
import time
import tracemalloc
import pandas as pd
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
REQUIRED = {"station", "date", "hour", "pm25", "pm10", "no2", "temperature", "temperature_unit"}
METRICS = ("pm25", "pm10", "no2", "temperature_c")


def parse_number(raw):
    """Convert a CSV value to float; blanks, missing markers and text become None."""
    if raw is None or str(raw).strip().upper() in {"", "NA", "N/A", "NULL"}:
        return None
    try:
        value = float(raw)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def clean_rows(path):
    """Read, validate, de-duplicate, unit-convert and impute one station CSV."""
    path = Path(path)
    counters = Counter()
    accepted = {}
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED - headers
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        for line_number, row in enumerate(reader, start=2):
            station = (row.get("station") or "").strip().title()
            if not station:
                counters["rejected_empty_station"] += 1
                continue
            try:
                parsed_date = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").date()
                day = parsed_date.isoformat()
            except ValueError:
                counters["rejected_invalid_date"] += 1
                continue
            try:
                hour = int((row.get("hour") or "").strip())
                if not 0 <= hour <= 23:
                    raise ValueError
            except ValueError:
                counters["rejected_invalid_hour"] += 1
                continue

            values = {}
            for col in ("pm25", "pm10", "no2"):
                val = parse_number(row.get(col))
                if val is None:
                    counters[f"missing_or_non_numeric_{col}"] += 1
                elif val < 0 or val > 999:
                    counters[f"impossible_{col}"] += 1
                    val = None
                values[col] = val

            temp = parse_number(row.get("temperature"))
            unit = (row.get("temperature_unit") or "C").strip().upper()
            if temp is None:
                counters["missing_or_non_numeric_temperature"] += 1
            elif unit == "F":
                temp = (temp - 32.0) * 5.0 / 9.0
                counters["fahrenheit_converted"] += 1
            elif unit != "C":
                counters["unknown_temperature_unit"] += 1
                temp = None
            if temp is not None and not -50 <= temp <= 70:
                counters["impossible_temperature"] += 1
                temp = None

            record = {
                "station": station, "date": day, "hour": hour,
                "pm25": values["pm25"], "pm10": values["pm10"], "no2": values["no2"],
                "temperature_c": temp, "source_unit": unit if unit in {"C", "F"} else "C"
            }
            key = (station, day, hour)
            if key in accepted:
                counters["duplicate_rows_skipped"] += 1
                if accepted[key] != record:
                    counters["conflicting_duplicate_rows"] += 1
                continue
            accepted[key] = record

    rows = sorted(accepted.values(), key=lambda r: (r["station"], r["date"], r["hour"]))

    # Compute correct station-specific medians from valid values, then forward-fill in time.
    medians = {}
    for station in sorted({r["station"] for r in rows}):
        station_rows = [r for r in rows if r["station"] == station]
        for metric in METRICS:
            valid = [r[metric] for r in station_rows if r[metric] is not None]
            medians[(station, metric)] = statistics.median(valid) if valid else None

    previous = {}
    for row in rows:
        station = row["station"]
        assert 0 <= row["hour"] <= 23
        for pollutant in ("pm25", "pm10", "no2"):
            assert row[pollutant] is None or 0 <= row[pollutant] <= 999
        for metric in METRICS:
            key = (station, metric)
            if row[metric] is None:
                replacement = previous.get(key)
                if replacement is None:
                    replacement = medians.get(key)
                row[metric] = replacement
                if replacement is not None:
                    counters[f"imputed_{metric}"] += 1
            else:
                previous[key] = row[metric]
    return rows, counters


def write_csv(path, rows):
    fields = ["station", "date", "hour", "pm25", "pm10", "no2", "temperature_c"]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def create_database(rows):
    db_path = OUT / "air_quality.sqlite"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
        CREATE TABLE stations (
            station_id INTEGER PRIMARY KEY,
            station_name TEXT NOT NULL UNIQUE,
            temperature_unit_received TEXT NOT NULL CHECK(temperature_unit_received IN ('C','F'))
        );
        CREATE TABLE readings (
            station_id INTEGER NOT NULL,
            reading_date TEXT NOT NULL,
            hour INTEGER NOT NULL CHECK(hour BETWEEN 0 AND 23),
            pm25 REAL, pm10 REAL, no2 REAL, temperature_c REAL,
            PRIMARY KEY(station_id, reading_date, hour),
            FOREIGN KEY(station_id) REFERENCES stations(station_id)
        );
    """)
    units = {}
    for row in rows:
        units.setdefault(row["station"], row["source_unit"])
    con.executemany(
        "INSERT INTO stations(station_name, temperature_unit_received) VALUES (?,?)",
        [(name, units[name]) for name in sorted(units)]
    )
    ids = {name: sid for sid, name in con.execute("SELECT station_id, station_name FROM stations")}
    con.executemany(
        "INSERT INTO readings VALUES (?,?,?,?,?,?,?)",
        [(ids[r["station"]], r["date"], r["hour"], r["pm25"], r["pm10"], r["no2"], r["temperature_c"]) for r in rows]
    )
    con.execute("CREATE INDEX idx_readings_station_date ON readings(station_id, reading_date)")
    con.commit()
    return con



def benchmark_cleaning_scales():
    """Compare CSV-loop cleaning + two-pass min-max scaling with pandas vectorised cleaning/scaling."""
    results = []
    with tempfile.TemporaryDirectory(prefix="co5_b1_clean_") as temp_dir:
        for size in (1_000, 100_000, 1_000_000):
            source = Path(temp_dir) / f"cleaning_{size}.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["station", "date", "hour", "pm25"])
                for i in range(size):
                    value = float(i % 180 + 1)
                    if i % 997 == 0:
                        value = "NA"
                    elif i % 4019 == 0:
                        value = -5
                    elif i % 5003 == 0:
                        value = 1200
                    writer.writerow([f"Station{i % 12:02d}", "2026-10-01", i % 24, value])

            # Plain CSV method: first pass finds valid min/max; second pass applies scaling.
            tracemalloc.start()
            start = time.perf_counter()
            low, high, valid_csv = float("inf"), float("-inf"), 0
            with source.open("r", newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    raw = (row["pm25"] or "").strip()
                    try:
                        number = float(raw)
                    except ValueError:
                        continue
                    if 0 <= number <= 999:
                        low, high = min(low, number), max(high, number)
                        valid_csv += 1
            csv_scaled_sum = 0.0
            if valid_csv:
                with source.open("r", newline="", encoding="utf-8") as handle:
                    for row in csv.DictReader(handle):
                        raw = (row["pm25"] or "").strip()
                        try:
                            number = float(raw)
                        except ValueError:
                            continue
                        if 0 <= number <= 999:
                            csv_scaled_sum += 0.0 if high == low else (number-low)/(high-low)
            csv_seconds = time.perf_counter() - start
            _, csv_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Pandas method: replace/parse missing values, filter, drop missing and scale vectorially.
            start = time.perf_counter()
            frame = pd.read_csv(source)
            replaced = frame["pm25"].replace({"NA": pd.NA, "": pd.NA})
            numeric = pd.to_numeric(replaced, errors="coerce")
            valid_values = numeric[(numeric >= 0) & (numeric <= 999)].dropna()
            valid_pandas = int(valid_values.count())
            if valid_pandas:
                scaled = ((valid_values-valid_values.min())/(valid_values.max()-valid_values.min())
                          if valid_values.max() != valid_values.min() else valid_values*0)
                pandas_scaled_sum = float(scaled.sum())
            else:
                pandas_scaled_sum = 0.0
            pandas_seconds = time.perf_counter() - start
            pandas_bytes = int(frame.memory_usage(index=True, deep=True).sum()
                               + numeric.memory_usage(index=True, deep=True)
                               + valid_values.memory_usage(index=True, deep=True))
            if valid_csv != valid_pandas or abs(csv_scaled_sum-pandas_scaled_sum) > 1e-6:
                raise AssertionError(f"CSV and pandas cleaning/normalisation disagree for {size} rows")
            results.append({
                "rows": size, "valid_rows": valid_csv,
                "csv_two_pass_seconds": csv_seconds, "csv_peak_tracemalloc_bytes": csv_peak,
                "pandas_vectorised_seconds": pandas_seconds, "pandas_frame_series_bytes": pandas_bytes
            })
            print(f"Cleaning + min-max benchmark {size:,} rows: CSV {csv_seconds:.4f}s; pandas {pandas_seconds:.4f}s; valid={valid_csv}")

    with (OUT / "b1_cleaning_benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["rows", "valid_rows", "csv_two_pass_seconds", "csv_peak_tracemalloc_bytes", "pandas_vectorised_seconds", "pandas_frame_series_bytes"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(results)
    print(f"CSV-vs-pandas cleaning and normalisation measurements saved to {OUT / 'b1_cleaning_benchmark.csv'}")

def main():
    edge_path = DATA / "cleaning_edge_cases.csv"
    monthly_path = DATA / "station_readings_october.csv"

    print("B1 – SMALL EDGE-CASE FILE: BEFORE CLEANING")
    with edge_path.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.DictReader(handle))
    for row in raw_rows:
        print(row)
    edge_clean, edge_counts = clean_rows(edge_path)
    print("\nB1 – SMALL EDGE-CASE FILE: AFTER CLEANING")
    for row in edge_clean:
        print(row)
    print("\nEdge-case quality counters:", dict(edge_counts))
    write_csv(OUT / "edge_cases_cleaned.csv", edge_clean)

    monthly_clean, monthly_counts = clean_rows(monthly_path)
    write_csv(OUT / "october_cleaned.csv", monthly_clean)
    with monthly_path.open("r", newline="", encoding="utf-8") as handle:
        monthly_input_count = sum(1 for _ in csv.DictReader(handle))
    print(f"\nMonthly input rows: {monthly_input_count}")
    print(f"Monthly cleaned rows: {len(monthly_clean)}")
    print("Monthly quality counters:", dict(monthly_counts))

    con = create_database(monthly_clean)
    queries = [
        ("Q1 – Adyar October average PM2.5",
         """SELECT AVG(r.pm25) FROM readings r JOIN stations s ON s.station_id=r.station_id
            WHERE s.station_name=? AND r.reading_date BETWEEN ? AND ?""",
         ("Adyar", "2026-10-01", "2026-10-31")),
        ("Q2 – Highest station/day mean PM2.5",
         """SELECT s.station_name, r.reading_date, AVG(r.pm25) AS daily_mean
            FROM readings r JOIN stations s ON s.station_id=r.station_id
            GROUP BY s.station_name, r.reading_date ORDER BY daily_mean DESC LIMIT 1""", ()),
        ("Q3 – Valid PM2.5 readings per station",
         """SELECT s.station_name, COUNT(r.pm25) FROM readings r
            JOIN stations s ON s.station_id=r.station_id GROUP BY s.station_name ORDER BY s.station_name""", ())
    ]
    with (OUT / "sql_results.txt").open("w", encoding="utf-8") as log:
        for title, sql, params in queries:
            result = con.execute(sql, params).fetchall()
            print(title, result)
            log.write(title + "\n" + repr(result) + "\n\n")

    daily = con.execute("""SELECT s.station_name, r.reading_date,
        MIN(r.pm25), MAX(r.pm25), AVG(r.pm25), COUNT(r.pm25)
        FROM readings r JOIN stations s ON s.station_id=r.station_id
        GROUP BY s.station_name, r.reading_date ORDER BY s.station_name, r.reading_date""").fetchall()
    with (OUT / "daily_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["station","date","pm25_min","pm25_max","pm25_mean","valid_reading_count"])
        writer.writerows(daily)

    # Chart 1 – city-wide daily PM2.5 trend.
    trend = con.execute("""SELECT reading_date, AVG(pm25) FROM readings
        GROUP BY reading_date ORDER BY reading_date""").fetchall()
    date_values = [datetime.strptime(r[0], "%Y-%m-%d") for r in trend]
    plt.figure(figsize=(10,5)); plt.plot(date_values,[r[1] for r in trend], marker="o", markersize=3)
    plt.title("Daily Mean PM2.5 – October 2026"); plt.xlabel("Date"); plt.ylabel("Mean PM2.5 (µg/m³)")
    plt.xticks(rotation=45); plt.tight_layout(); plt.savefig(OUT/"01_pm25_monthly_trend.png", dpi=150); plt.close()

    # Chart 2 – mean PM2.5 by station.
    by_station = con.execute("""SELECT s.station_name, AVG(r.pm25) FROM readings r
        JOIN stations s ON s.station_id=r.station_id GROUP BY s.station_name ORDER BY s.station_name""").fetchall()
    plt.figure(figsize=(11,5)); plt.bar([r[0] for r in by_station],[r[1] for r in by_station])
    plt.title("Mean PM2.5 by Monitoring Station"); plt.xlabel("Station"); plt.ylabel("Mean PM2.5 (µg/m³)")
    plt.xticks(rotation=40, ha="right"); plt.tight_layout(); plt.savefig(OUT/"02_station_comparison.png", dpi=150); plt.close()

    # Chart 3 – temperature relationship.
    paired = con.execute("SELECT temperature_c, pm25 FROM readings WHERE temperature_c IS NOT NULL AND pm25 IS NOT NULL").fetchall()
    plt.figure(figsize=(7,5)); plt.scatter([r[0] for r in paired],[r[1] for r in paired], alpha=0.35, s=12)
    plt.title("Temperature vs PM2.5"); plt.xlabel("Temperature (°C)"); plt.ylabel("PM2.5 (µg/m³)")
    plt.tight_layout(); plt.savefig(OUT/"03_temperature_vs_pm25.png", dpi=150); plt.close()

    # Chart 4 – PM2.5 distribution by hour.
    by_hour = con.execute("SELECT hour, pm25 FROM readings WHERE pm25 IS NOT NULL ORDER BY hour").fetchall()
    grouped = {h: [] for h in range(24)}
    for hour, value in by_hour: grouped[hour].append(value)
    plt.figure(figsize=(11,5)); plt.boxplot([grouped[h] for h in range(24)], positions=list(range(24)), showfliers=False)
    plt.title("PM2.5 Distribution by Hour of Day"); plt.xlabel("Hour of day (0–23)"); plt.ylabel("PM2.5 (µg/m³)")
    plt.tight_layout(); plt.savefig(OUT/"04_hourly_pm25_boxplot.png", dpi=150); plt.close()

    correlation = statistics.correlation([r[0] for r in paired],[r[1] for r in paired]) if len(paired)>1 else float("nan")
    top_station = max(by_station, key=lambda r:r[1])
    top_hour = max(grouped, key=lambda h: statistics.median(grouped[h]) if grouped[h] else float("-inf"))
    peak_day = max(trend, key=lambda r:r[1])
    interpretation = (
        f"1. Line chart: the highest city-wide daily mean in this sample occurs on {peak_day[0]} ({peak_day[1]:.2f} µg/m³). The daily line shows how the city-wide mean changes across October.\n"
        f"2. Bar chart: {top_station[0]} has the highest mean station reading in this sample ({top_station[1]:.2f} µg/m³). Bar heights make differences between stations easy to compare.\n"
        f"3. Scatter plot: the Pearson correlation between temperature and PM2.5 in this sample is {correlation:.3f}. This indicates the strength and direction of a linear association, not proof that temperature causes pollution.\n"
        f"4. Box plot: hour {top_hour:02d} has the highest median PM2.5 in this sample. The box plots also show spread and outliers across hours.\n"
        "These results describe the supplied synthetic demonstration dataset only; they must not be presented as real city measurements.\n"
    )
    (OUT/"chart_interpretation.txt").write_text(interpretation, encoding="utf-8")
    print("\n" + interpretation)
    benchmark_cleaning_scales()
    print(f"Saved database, cleaned CSVs, SQL results, summary, charts and cleaning benchmarks in {OUT}")
    con.close()

if __name__ == "__main__":
    main()
