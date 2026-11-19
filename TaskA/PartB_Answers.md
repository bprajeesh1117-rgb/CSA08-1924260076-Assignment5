# PART B – IMPLEMENTATION AND EXPERIMENTAL INVESTIGATION (25 MARKS)

## B1 – Implement and validate the cleaning pipeline (7 marks)

### B1.1 Before and after cleaning (2 marks)

Run `python TaskB1/task_b1.py`. The small file `TaskB1/data/cleaning_edge_cases.csv` deliberately contains blank and `NA` values, negative and greater-than-999 pollutant values, non-numeric text, Fahrenheit temperatures, an exact duplicate key, inconsistent station spelling, an invalid date and an invalid hour. The script prints the raw rows and the cleaned rows. It also prints counters showing how many rows/values were rejected, duplicated, converted or imputed. The larger October file contains 12 stations and hourly readings for 30 days so that monthly charts can be produced.

The cleaner performs these operations in order: schema validation, station-name normalisation, date/hour validation, numeric conversion, pollutant range validation, Fahrenheit conversion, duplicate detection, chronological sorting, forward fill and station-median fallback. The median is calculated with `statistics.median`, which handles both odd and even-sized lists correctly. The outputs `edge_cases_cleaned.csv` and `october_cleaned.csv` provide before/after evidence.

### B1.2 Compare with the design (1 mark)

The code follows the Part A rules. It uses the composite station/date/hour key to remove duplicates. Invalid pollutant values are marked missing and then handled using the same imputation rule as other missing values; this preserves other valid measurements in that hourly record. Invalid date/hour records are rejected because they cannot be grouped correctly. The assignment's `>999` requirement is also tested in the separate completed-code program.

### B1.3 Store and query (2 marks)

The script creates `stations` and `readings` tables, enables foreign-key checking, inserts stations and readings using `executemany`, and creates a date/station lookup index. It runs the three A1.3 questions: Adyar's October mean, the station/date with the highest daily mean, and the valid PM2.5 count per station. Exact results are saved to `outputs/sql_results.txt`. The daily min/max/mean/count table is saved as `outputs/daily_summary.csv`.

### B1.4 Visualise (2 marks)

Four labelled charts are saved in `outputs/`:
1. `01_pm25_monthly_trend.png` – line chart of city-wide daily mean PM2.5.
2. `02_station_comparison.png` – bar chart of mean PM2.5 by station.
3. `03_temperature_vs_pm25.png` – scatter plot of temperature against PM2.5.
4. `04_hourly_pm25_boxplot.png` – box plots of PM2.5 grouped by hour.

The program calculates a short interpretation for the generated sample and stores it in `outputs/chart_interpretation.txt`. These charts use a deterministic synthetic demonstration dataset, not real measurements from Chennai; state this clearly in the report.

**Complete the Code:** `TaskB1/complete_code_b1.py` completes both TODOs. TODO 1 uses `csv.DictReader`, skips blank/`NA`, negative and greater-than-999 PM2.5 values, and converts valid values to float. TODO 2 applies min–max normalisation and handles empty or constant input safely.

Expected output from the supplied TODO sample:

```text
[('Adyar', '2026-10-01', 48.0), ('Guindy', '2026-10-01', 95.0), ('Guindy', '2026-10-03', 121.0)]
[0.0, 0.644, 1.0]
```

**Alternative: pandas cleaning.** A pandas solution reads the CSV using `read_csv`, replaces text missing markers with `NaN`, converts columns using `to_numeric(errors='coerce')`, filters invalid ranges, calls `drop_duplicates`, converts Fahrenheit values with a vectorised expression, and normalises with `(series-series.min())/(series.max()-series.min())`. These operations are generally O(n) per column/pass; median computation may require sorting (O(n log n) in a straightforward implementation). Pandas keeps a DataFrame and intermediate columns in memory, so its memory use is O(n). A row-by-row CSV loop can use less memory if it processes rows incrementally; vectorised pandas operations may be faster for large columns but require memory. The program measures both methods at 1,000, 100,000 and 1,000,000 rows. The CSV method uses two passes to find the valid minimum/maximum and then calculate min–max values without storing all readings. CSV peak memory is recorded with `tracemalloc`; pandas memory is estimated from the DataFrame and intermediate Series `memory_usage(deep=True)`. These are not perfectly equivalent memory measures because `tracemalloc` does not capture every native NumPy allocation. Use the measured values in `outputs/b1_cleaning_benchmark.csv` and, when running on your laptop, replace them with your own results.

Example measurements from the prepared execution environment:

| Rows | CSV two-pass time (s) | CSV Python-traced peak (bytes) | pandas vectorised time (s) | pandas frame/Series bytes |
|---:|---:|---:|---:|---:|
| 1,000 | 0.0106 | 39,697 | 0.0031 | 157,232 |
| 100,000 | 1.2467 | 50,020 | 0.0591 | 15,697,960 |
| 1,000,000 | 12.4511 | 48,470 | 0.3073 | 156,977,048 |

These are example timings from the prepared execution environment, not guaranteed results on your laptop. The two memory columns use different measurement techniques and should not be treated as a perfectly like-for-like comparison. Replace this table with your local values before final submission.


## B2 – Engineer adversarial data (5 marks)

Run `python TaskB2/task_b2.py`.

- Missing-column file: reports the missing `date` and `pm25` headings.
- Wrong delimiter: a semicolon file read with a comma delimiter appears as one header field, so the required columns are reported missing.
- Different encoding: UTF-16 bytes decoded as UTF-8 raise `UnicodeDecodeError`, which the program catches and prints.
- Empty file: no header is found.
- Quoted station name: concatenating `King's Park` into SQL breaks the quoted SQL literal; the parameterised query finds the station correctly.
- Injection string: concatenating `Adyar' OR '1'='1` changes the SQL condition and returns all rows in the isolated test database. A parameterised query treats the complete input as one station name and finds no matching station, returning `None` for its average.

The completed TODO program `TaskB2/complete_code_b2.py` uses one `executemany` call with `?` placeholders, commits the transaction and uses a parameterised `SELECT`. Its expected output is:

```text
54.0 108.0
None
```

The adversarial sentiment examples show additional limits: sarcasm can be labelled neutral because the word is not in the lexicon; double negatives can be misinterpreted because only the immediately preceding word is checked; mixed positive and negative opinions may cancel to neutral and lose the contrast.

`executemany()` and a loop containing n calls to `execute()` both insert n rows and are O(n) in row count. `executemany()` reduces Python-to-SQLite call overhead and is usually more efficient for batches. The unsafe SQL concatenation is shown only on a temporary in-memory database to demonstrate the vulnerability; never use it in an actual application.

## B3 – Loops vs libraries vs SQL (8 marks)

Run `python TaskB3/task_b3.py`.

### B3.1 Correctness on small data (2 marks)

The Python implementation reads the CSV using `csv.DictReader`, groups readings by `(station, day)` and uses `statistics.mean`. The pandas implementation uses `read_csv` and `groupby`. The SQL implementation reads the same CSV into SQLite using `executemany` and calculates the daily mean with `GROUP BY` and `AVG`. The program compares the result keys and every mean within a floating-point tolerance. It also checks that the running-sum/count alternative agrees.

### B3.2 Increase data size (2 marks)

The generator creates 24 readings per day for 365 days, which is 8,760 readings per station. The program tests 1, 12 and 120 stations (8,760; 105,120; and 1,051,200 readings). It measures each complete method using `time.perf_counter`. SQL timing includes CSV ingestion into SQLite plus the GROUP BY query; it is not a query-only comparison. The measured example run from the prepared execution environment was:

| Stations | Readings | Python CSV loops | pandas | SQLite load + GROUP BY |
|---:|---:|---:|---:|---:|
| 1 | 8,760 | 0.0151 s | 0.0177 s | 0.0210 s |
| 12 | 105,120 | 0.1636 s | 0.0550 s | 0.3583 s |
| 120 | 1,051,200 | 1.9439 s | 0.3699 s | 2.8767 s |

These are example measurements from the prepared execution environment, not guaranteed timings for your laptop. The actual timings from your laptop are saved in `outputs/b3_benchmark_results.csv`; use your local results in the final submitted report.

### B3.3 Profile (2 marks)

The plain-Python CSV function is profiled using `cProfile`; the cumulative-time report is saved in `outputs/cprofile_report.txt`. Read the top entries from your own run and name the function with the largest cumulative time. This may vary by Python version and computer.

### B3.4 Engineering trade-off (2 marks)

For a quick one-time analysis, pandas is convenient because the code is short and `groupby` is optimised. For a daily automated report with persistent data and repeated filters, SQLite is appropriate because the readings remain stored and can be queried with indexes. A streaming Python loop is useful when memory is limited, but the implementation here stores group values to calculate `statistics.mean`.

**Alternative running-sum/count algorithm:** Read each CSV row once. For each `(station, day)` key, update a running total and count. At the end, divide total by count. Both approaches take O(n) time. Storing all readings in lists uses O(n) space. Running aggregates use O(stations × days) space because only sum and count are stored per group.

## B4 – Final engineering decision (5 marks)

Run `python TaskB4/task_b4.py`.

### B4.1 Practical strategy (2 marks)

The script processes 50 complaints using a lexicon scorer with immediate-negation handling. It also creates a frequency-based extractive summary and a first-five-sentences baseline for comparison. The file `TaskB4/data/manual_complaint_labels.csv` has 50 blank labels. Read each complaint yourself and fill each `your_label` cell with exactly `positive`, `negative` or `neutral`; rerun the program to calculate how many of your labels match the program. The program deliberately does not report a made-up human-agreement percentage before you complete this review.

### B4.2 Database index (1 mark)

The program inserts 200,000 sample rows into an in-memory SQLite table and runs the same station/day average query 200 times before and after creating `CREATE INDEX idx_station_day ON readings(station, day)`. It prints both elapsed times and `EXPLAIN QUERY PLAN` output. The plan should change from a table scan to an indexed search. The exact timing improvement depends on machine, cache and SQLite version; report the measurements from your run. In the prepared example run, 200 queries took about 1.5875 s before the index and 0.0003 s after it; the query plan changed from `SCAN readings` to `SEARCH readings USING INDEX idx_station_day`. Replace these example figures with your own output.

### B4.3 Production decision (2 marks)

There are 12 current stations plus 100 additional stations, giving 112 stations. At 96 quarter-hour readings per station per day, the system receives 10,752 readings per day and 3,924,480 readings in 365 days. Use SQLite with station/date indexes for the assignment-scale prototype, batch inserts, constraints and a validation/quarantine path for bad records. Use SQL for routine daily/monthly aggregation and pandas for offline exploration. At larger sustained scale, monitor database size and query latency and consider a server database/partitioning only when measurements justify it.

The lexicon scorer is transparent and inexpensive, so it can be retained for basic triage, but it is not sufficient as the only method for 50,000 complaints per month because sarcasm, mixed opinions and complex negation are common failure cases. Label a representative dataset and evaluate a trained classifier (for example Naive Bayes) on held-out complaints. Use human review for uncertain or high-impact cases. A larger language model may improve context handling but needs more memory, compute, latency and privacy assessment.

**Alternative summary:** If the sentence list is already available, selecting the first k sentences is O(1) selection work (and uses O(k) output space); splitting the original text into sentences still requires scanning the text. Frequency-based extraction must tokenise and count words, generally O(words) time and O(vocabulary) frequency storage, then rank sentences. The first-k method is faster but can omit the central point if it appears later. Frequency selection is more content-aware but may favour repeated words. Compare the two outputs on your 50 complaints and discuss the difference.
