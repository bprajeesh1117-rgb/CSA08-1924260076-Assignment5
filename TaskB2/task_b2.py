import csv
import io
import sqlite3
import re
from pathlib import Path


def inspect_csv(label, content, encoding="utf-8", delimiter=","):
    print(f"\n{label}")
    try:
        decoded = content.decode(encoding) if isinstance(content, bytes) else content
        reader = csv.DictReader(io.StringIO(decoded), delimiter=delimiter)
        required = {"station", "date", "pm25"}
        if not reader.fieldnames:
            print("ERROR: empty file or missing header")
        elif not required.issubset(set(reader.fieldnames)):
            print("ERROR: missing columns", sorted(required-set(reader.fieldnames)))
        else:
            print("Parsed rows:", list(reader))
    except (UnicodeDecodeError, csv.Error) as error:
        print("ERROR:", type(error).__name__, str(error))


def sentiment_score(text):
    positive = {"good", "clean", "fast", "helpful", "improved"}
    negative = {"bad", "dirty", "slow", "rude", "smoke", "broken"}
    negators = {"not", "never", "no"}
    words = re.findall(r"[a-z0-9']+", text.lower())
    total = 0
    for index, word in enumerate(words):
        value = 1 if word in positive else -1 if word in negative else 0
        if index > 0 and words[index-1] in negators:
            value *= -1
        total += value
    return total


def sentiment_label(text):
    value = sentiment_score(text)
    return "positive" if value > 0 else "negative" if value < 0 else "neutral"


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parent / "data"
    inspect_csv("Missing column", (data_dir / "missing_column.csv").read_text(encoding="utf-8"))
    inspect_csv("Wrong delimiter", (data_dir / "wrong_delimiter.csv").read_text(encoding="utf-8"))
    inspect_csv("Different encoding (UTF-16 read as UTF-8)", (data_dir / "different_encoding_utf16.csv").read_bytes(), encoding="utf-8")
    inspect_csv("Empty file", (data_dir / "empty_file.csv").read_bytes())

    readings = [("Adyar", "2026-10-01", 48.0), ("Guindy", "2026-10-01", 95.0),
                ("Guindy", "2026-10-03", 121.0), ("Adyar", "2026-10-04", 60.0),
                ("King's Park", "2026-10-01", 40.0)]
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE aq (station TEXT, day TEXT, pm25 REAL)")
    # Required bulk insertion: one executemany call using ? placeholders, then commit.
    con.executemany("INSERT INTO aq VALUES (?, ?, ?)", readings)
    con.commit()

    def station_average(name):
        row = con.execute("SELECT AVG(pm25) FROM aq WHERE station = ?", (name,)).fetchone()
        return row[0]

    print("\nExpected completed-code query results:")
    print(station_average("Adyar"), station_average("Guindy"))
    print(station_average("Adyar' OR '1'='1"))

    # B2 required comparison: concatenated SQL with a quote-containing station name.
    quote_name = "King's Park"
    unsafe_quote_sql = "SELECT station, pm25 FROM aq WHERE station = '" + quote_name + "'"
    try:
        print("Unsafe query for a quote-containing name:", con.execute(unsafe_quote_sql).fetchall())
    except sqlite3.Error as error:
        print("Unsafe query for a quote-containing name failed:", error)
    print("Safe query for a quote-containing name:", con.execute("SELECT station, pm25 FROM aq WHERE station = ?", (quote_name,)).fetchall())

    # B2 required SQL-injection demonstration; run only against this in-memory test database.
    attack = "Adyar' OR '1'='1"
    unsafe_injection_sql = "SELECT station, day, pm25 FROM aq WHERE station = '" + attack + "'"
    print("Unsafe concatenated SQL result count:", len(con.execute(unsafe_injection_sql).fetchall()))
    print("Safe parameterised injection result:", con.execute("SELECT AVG(pm25) FROM aq WHERE station = ?", (attack,)).fetchone()[0])

    print("\nSentiment adversarial tests:")
    adversarial = [
        "Great job, officials!",                         # sarcasm can be neutral
        "This is not never good.",                       # double negative/negation scope
        "The air is clean but the roads are dirty.",        # mixed opinion may cancel to neutral
        "Not good near the factory.",                    # simple negation should be negative
    ]
    for sentence in adversarial:
        print(f"{sentiment_label(sentence):8} | {sentence}")
    print("Limitation: a small lexicon misses sarcasm and complex/double negation and may cancel mixed opinions.")
    con.close()
