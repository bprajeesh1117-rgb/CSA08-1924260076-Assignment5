import csv
import sqlite3
import statistics
import time
import cProfile
import pstats
import io
import tempfile
from pathlib import Path
from datetime import date, timedelta
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def generate_csv(path, station_count, days=365):
    """Generate 24 hourly rows per station/day: 8,760 readings per station/year."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["station", "day", "hour", "pm25"])
        for station_index in range(station_count):
            station = f"Station{station_index+1:03d}"
            for day_index in range(days):
                day_text = (date(2026, 1, 1) + timedelta(days=day_index)).isoformat()
                for hour in range(24):
                    value = float((station_index*7 + day_index*3 + hour) % 180 + 1)
                    writer.writerow([station, day_text, hour, value])


def python_csv_group(path):
    """Plain Python + csv module; stores each group's readings before taking mean."""
    buckets = {}
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["station"], row["day"])
            buckets.setdefault(key, []).append(float(row["pm25"]))
    return {key: statistics.mean(values) for key, values in buckets.items()}


def pandas_group(path):
    frame = pd.read_csv(path)
    grouped = frame.groupby(["station", "day"], sort=True)["pm25"].mean()
    return {(station, day): float(value) for (station, day), value in grouped.items()}


def sql_group(path):
    """SQL time includes CSV ingestion + executemany + GROUP BY query."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE readings(station TEXT, day TEXT, hour INTEGER, pm25 REAL)")
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        con.executemany(
            "INSERT INTO readings VALUES (?, ?, ?, ?)",
            ((r["station"], r["day"], int(r["hour"]), float(r["pm25"])) for r in reader)
        )
    result = {(station, day): float(mean) for station, day, mean in con.execute(
        "SELECT station, day, AVG(pm25) FROM readings GROUP BY station, day")}
    con.close()
    return result


def running_sum_count_csv(path):
    """Alternative one-pass aggregation: O(n) time and O(stations × days) space."""
    aggregate = {}
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["station"], row["day"])
            total, count = aggregate.get(key, (0.0, 0))
            aggregate[key] = (total + float(row["pm25"]), count + 1)
    return {key: total/count for key, (total, count) in aggregate.items()}


def outputs_match(reference, candidate):
    return reference.keys() == candidate.keys() and all(
        abs(reference[key] - candidate[key]) < 1e-9 for key in reference
    )


def benchmark_file(path, stations, readings):
    timings = {}
    results = {}
    for label, function in [("Python csv loops", python_csv_group),
                            ("pandas read_csv/groupby", pandas_group),
                            ("SQLite load + GROUP BY", sql_group)]:
        start = time.perf_counter()
        results[label] = function(path)
        timings[label] = time.perf_counter() - start
    reference = results["Python csv loops"]
    for label, result in results.items():
        if not outputs_match(reference, result):
            raise AssertionError(f"Daily means do not match for {label}")
    print(f"\n{stations} station(s), {readings:,} readings")
    for label, seconds in timings.items():
        print(f"{label:27} {seconds:.4f} s")
    return timings


if __name__ == "__main__":
    records = []
    with tempfile.TemporaryDirectory(prefix="co5_b3_") as temp_dir:
        temp = Path(temp_dir)
        # B3.1: small CSV correctness check using the three requested methods.
        small_path = temp / "small.csv"
        generate_csv(small_path, station_count=2, days=3)
        small_python = python_csv_group(small_path)
        small_pandas = pandas_group(small_path)
        small_sql = sql_group(small_path)
        small_running = running_sum_count_csv(small_path)
        print("Small-data correctness (CSV loops == pandas == SQL):",
              outputs_match(small_python, small_pandas) and outputs_match(small_python, small_sql))
        print("Running-sum alternative agrees:", outputs_match(small_python, small_running))

        # B3.2: 1, 12 and 120 stations for 365 days × 24 hours = 8,760 rows/station.
        for count in (1, 12, 120):
            csv_path = temp / f"stations_{count}.csv"
            generate_csv(csv_path, count)
            elapsed = benchmark_file(csv_path, count, count*365*24)
            records.append({"stations": count, "readings": count*365*24, **elapsed})

        # B3.3: profile the required plain-Python csv implementation on 12 stations.
        profile_path = temp / "profile_12_stations.csv"
        generate_csv(profile_path, 12, days=30)
        profiler = cProfile.Profile()
        profiler.enable()
        python_csv_group(profile_path)
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(20)
        profile_text = stream.getvalue()
        (OUT / "cprofile_report.txt").write_text(profile_text, encoding="utf-8")
        print("\nTop cProfile entries (cumulative time):")
        print("\n".join(profile_text.splitlines()[:18]))

    with (OUT / "b3_benchmark_results.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["stations", "readings", "Python csv loops", "pandas read_csv/groupby", "SQLite load + GROUP BY"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records: writer.writerow(row)
    print(f"\nBenchmark table saved to {OUT / 'b3_benchmark_results.csv'}")
    print(f"Profile report saved to {OUT / 'cprofile_report.txt'}")
