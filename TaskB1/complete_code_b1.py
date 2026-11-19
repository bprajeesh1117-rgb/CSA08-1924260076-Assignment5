import csv
import io

RAW = """station,date,pm25
Adyar,2026-10-01,48
Adyar,2026-10-02,NA
Adyar,2026-10-03,
Guindy,2026-10-01,95
Guindy,2026-10-02,-5
Guindy,2026-10-03,121
Guindy,2026-10-04,1200
"""

def load_clean(text):
    """Return (station, date, pm25) tuples for valid readings only."""
    rows = []
    # TODO 1: Read with csv.DictReader; skip empty, NA, negative and >999 values.
    for row in csv.DictReader(io.StringIO(text)):
        raw = (row["pm25"] or "").strip()
        if raw.upper() in {"", "NA"}:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value < 0 or value > 999:
            continue
        rows.append((row["station"], row["date"], value))
    return rows

def min_max(values):
    # TODO 2: Scale to 0–1 and round to three decimals.
    values = list(values)
    if not values:
        return []
    low, high = min(values), max(values)
    if high == low:
        return [0.0 for _ in values]
    return [round((value-low)/(high-low), 3) for value in values]

clean = load_clean(RAW)
print(clean)
print(min_max([pm for _, _, pm in clean]))
