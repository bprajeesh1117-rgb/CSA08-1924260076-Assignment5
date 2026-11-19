import csv
import sqlite3
import time
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
POSITIVE = {"good", "clean", "fast", "helpful", "improved"}
NEGATIVE = {"bad", "dirty", "slow", "rude", "smoke", "broken"}
NEGATORS = {"not", "never", "no"}
STOP_WORDS = {"the", "is", "a", "an", "and", "was", "were", "to", "of", "in", "from", "it", "this", "that", "are", "near", "but", "for", "on", "after"}


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def score(text):
    """+1 per positive, -1 per negative; an immediately preceding negator flips it."""
    tokens = words(text)
    total = 0
    for index, token in enumerate(tokens):
        value = 1 if token in POSITIVE else -1 if token in NEGATIVE else 0
        if index > 0 and tokens[index-1] in NEGATORS:
            value *= -1
        total += value
    return total


def label(text):
    result = score(text)
    return "positive" if result > 0 else "negative" if result < 0 else "neutral"


def split_sentences(text):
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def extractive_summary(text, count=5):
    """Select sentences containing frequent non-stop words; preserve original order."""
    sentences = split_sentences(text)
    tokenised = [[w for w in words(sentence) if w not in STOP_WORDS] for sentence in sentences]
    frequencies = Counter(token for row in tokenised for token in row)
    scores = [sum(frequencies[token] for token in row) for row in tokenised]
    chosen = sorted(sorted(range(len(sentences)), key=lambda i: (-scores[i], i))[:count])
    return " ".join(sentences[i] for i in chosen)


def first_k_summary(text, count=5):
    """Baseline: select the first k sentences from an already split sentence list."""
    return " ".join(split_sentences(text)[:count])


def load_complaints():
    with (DATA / "complaints.csv").open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_manual_labels(complaints, prediction_by_id):
    path = DATA / "manual_complaint_labels.csv"
    with path.open("r", newline="", encoding="utf-8") as handle:
        human = {row["complaint_id"]: row["your_label"].strip().lower() for row in csv.DictReader(handle)}
    allowed = {"positive", "negative", "neutral"}
    missing = [row["complaint_id"] for row in complaints if human.get(row["complaint_id"]) not in allowed]
    if missing:
        print(f"\nManual agreement NOT calculated: {len(missing)} labels are still blank/invalid.")
        print("Read each complaint in data/complaints.csv, fill data/manual_complaint_labels.csv with positive/negative/neutral, and rerun B4.")
        return None
    agree = sum(prediction_by_id[row["complaint_id"]] == human[row["complaint_id"]] for row in complaints)
    print(f"Manual agreement: {agree}/{len(complaints)} = {agree/len(complaints)*100:.1f}%")
    return agree


def benchmark_index():
    """Measure the same station/day SELECT before and after a composite index."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE readings(station TEXT, day TEXT, pm25 REAL)")
    rows = ((f"Station{i%112:03d}", f"2026-10-{i%28+1:02d}", float(i%200)) for i in range(200_000))
    con.executemany("INSERT INTO readings VALUES (?,?,?)", rows)
    con.commit()
    query = "SELECT AVG(pm25) FROM readings WHERE station=? AND day=?"
    params = ("Station050", "2026-10-12")
    def measure():
        start = time.perf_counter()
        for _ in range(200): con.execute(query, params).fetchone()
        return time.perf_counter()-start
    plan_before = con.execute("EXPLAIN QUERY PLAN " + query, params).fetchall()
    before = measure()
    con.execute("CREATE INDEX idx_station_day ON readings(station, day)")
    con.commit()
    plan_after = con.execute("EXPLAIN QUERY PLAN " + query, params).fetchall()
    after = measure()
    con.close()
    return before, after, plan_before, plan_after


if __name__ == "__main__":
    complaint_rows = load_complaints()
    predictions = {}
    corpus = []
    print(f"Complaints processed: {len(complaint_rows)}")
    for row in complaint_rows:
        text = row["complaint_text"]
        predictions[row["complaint_id"]] = label(text)
        corpus.append(text)
        print(f"{predictions[row['complaint_id']]:8} | {text}")

    check_manual_labels(complaint_rows, predictions)
    combined = " ".join(corpus)
    print("\nExtractive frequency summary (top 5 sentences):")
    print(extractive_summary(combined, count=5))
    print("\nFirst-five-sentences baseline:")
    print(first_k_summary(combined, count=5))

    before, after, plan_before, plan_after = benchmark_index()
    print("\n200 query runs before composite index:", f"{before:.6f} s")
    print("200 query runs after composite index: ", f"{after:.6f} s")
    print("Query plan before index:", plan_before)
    print("Query plan after index: ", plan_after)
    print("\nProduction scale: 12 existing + 100 additional stations = 112 stations.")
    print("At 96 readings per station per day: 10,752 readings/day and 3,924,480 readings/year (365 days).")
