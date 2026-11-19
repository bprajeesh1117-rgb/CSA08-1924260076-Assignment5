# PART A – DATA AND PROGRAM DESIGN (25 MARKS)

All algorithms below use a structured pseudocode format: **Algorithm, Input, Output, Begin, numbered steps, control structures and End**. Use the exact heading style required by your SIMATS class notes if your faculty has supplied a separate template.

## A1 – Design the Data Acquisition (7 marks)

### A1.1 Inspect the source (2 marks)

Each station sends a comma-separated CSV file. The first row contains column headings, and each following row represents one hourly observation from one station. A suitable structure is:

`station,date,hour,pm25,pm10,no2,temperature,temperature_unit`

Example: `Adyar,2026-10-01,8,48,72,18,86,F`.

Expected quality problems:

| Problem | Example | How it affects the analysis |
|---|---|---|
| Blank reading | PM2.5 is empty | An average may be calculated from too few values. |
| Text missing marker | PM2.5 is `NA` | It cannot be averaged as a number. |
| Negative sensor value | PM2.5 = -5 | A pollutant concentration cannot be negative. |
| Impossibly large value | PM2.5 = 1200 | It may be a sensor or transmission fault. |
| Non-numeric text | PM2.5 = `high` | Numeric conversion fails. |
| Fahrenheit temperature | 86 °F instead of 30 °C | Mixing °F and °C gives invalid comparisons. |
| Duplicate station-time row | Same station/date/hour appears twice | It double-counts the observation. |
| Inconsistent station name | `adyar ` and `Adyar` | One station may be treated as two groups. |
| Invalid date | `2026-13-40` | The row cannot be placed in a correct daily/monthly group. |
| Invalid hour | Hour = 25 | The row is not a valid hourly reading. |

File-level problems such as missing headers, a wrong delimiter, an unexpected encoding and an empty file are tested separately in B2 because they affect the whole file rather than one reading.

### A1.2 Design the storage (3 marks)

Use two linked SQLite tables.

**Table 1: `stations`**

| Column | SQLite type | Constraint / purpose |
|---|---|---|
| `station_id` | INTEGER | Primary key; unique internal ID. |
| `station_name` | TEXT | NOT NULL and UNIQUE; canonical station name. |
| `temperature_unit_received` | TEXT | NOT NULL; records the source unit (`C` or `F`). |

**Table 2: `readings`**

| Column | SQLite type | Constraint / purpose |
|---|---|---|
| `station_id` | INTEGER | Foreign key to `stations.station_id`. |
| `reading_date` | TEXT | NOT NULL; ISO `YYYY-MM-DD`. |
| `hour` | INTEGER | NOT NULL; CHECK between 0 and 23. |
| `pm25` | REAL | Cleaned PM2.5; NULL only when no valid value can be obtained. |
| `pm10` | REAL | Cleaned PM10. |
| `no2` | REAL | Cleaned NO₂. |
| `temperature_c` | REAL | Temperature converted to Celsius. |

The readings table has a composite primary key `(station_id, reading_date, hour)` so that one station cannot have two accepted rows for the same hour. A foreign key connects each reading to a station. Enable `PRAGMA foreign_keys = ON` when using SQLite.

**CSV-to-table mapping:** `station` is trimmed and canonicalised, then stored once in `stations.station_name`; its generated `station_id` is placed in `readings.station_id`. `date` maps to `reading_date`; `hour` maps to `hour`; `pm25`, `pm10` and `no2` map to their REAL columns; `temperature` is converted if necessary and stored as `temperature_c`. The source unit is recorded in the station table.

**Algorithm A1 – Acquire and store station CSV data**

Input: Station CSV files. Output: Station and reading records stored in SQLite.

BEGIN
1. Open each station CSV file and read its header.
2. FOR each row DO
   - Read station name, date, hour, pollutant values and temperature unit.
   - Validate that the required columns exist.
   - Send the row to the cleaning procedure in Algorithm A2.
3. Insert each unique station into the stations table.
4. Obtain the station ID for each reading.
5. Insert cleaned readings into the readings table using parameter placeholders.
6. Commit the transaction.
END

### A1.3 CSV or SQL? (2 marks)

| Board question | CSV/Python approach | SQL approach |
|---|---|---|
| Average PM2.5 at Adyar in October | Read the CSV rows, filter station and date, add valid PM2.5 values and divide by the count. | `SELECT AVG(r.pm25) ... WHERE s.station_name=? AND r.reading_date BETWEEN ? AND ?`. |
| Station/day with highest mean PM2.5 | Read all files, group values by station and date, calculate means and find the largest. | `GROUP BY station_name, reading_date ORDER BY AVG(pm25) DESC LIMIT 1`. |
| Valid PM2.5 readings per station | Count non-missing PM2.5 values for each station in Python. | `SELECT station_name, COUNT(pm25) ... GROUP BY station_name`. |

For one small one-time analysis, CSV is simple. For repeated questions and daily reports, SQLite is preferable because it persists the cleaned data, supports constraints and can use indexes. If every question loads all CSV files into a pandas DataFrame, the scan takes O(n) time per question and the DataFrame uses O(n) memory. An indexed equality/range lookup is approximately O(log n) to find the matching index range, plus the cost of reading and aggregating the matching rows. CSV occupies disk space, but each fresh DataFrame requires memory while it is being analysed. SQLite stores the main dataset on disk and uses cache/query memory.

**Alternative (CSV + pandas):** use `pd.read_csv()` for each file, concatenate the DataFrames, filter the required station/date and call `.mean()` or `.groupby()`. The full scan is O(n) per question; memory is O(n) for the loaded DataFrame. An indexed SQL query avoids scanning unrelated rows for selective queries, although an aggregate still has to process the matching rows.

## A2 – Design the Cleaning and Normalisation (5 marks)

### A2.1 Cleaning rules (2 marks)

1. **Missing values:** Convert blank strings, `NA`, `N/A` and `NULL` to a missing value. After sorting each station by date and hour, forward-fill from the previous valid reading for the same station and measurement. If no previous reading exists, use the median of valid readings for that station and measurement. If the station has no valid value, leave it NULL and exclude it from that metric's average. Forward fill is suitable for a short gap; the median is robust against extreme values.
2. **Impossible values:** Set negative pollutant readings and pollutant readings above the stated plausibility limit of 999 to missing, record the rejection in a quality counter/log, and apply the missing-value rule. This prevents an impossible value entering the average. The limit is an assignment rule for this demonstration and should be replaced by the sensor's documented range in a real system.
3. **Duplicates:** Use `(station, date, hour)` as the unique key. Keep the first copy of an exact duplicate and count the duplicate. If a duplicate key has conflicting measurements, flag it and retain the first accepted record for this demonstration; a production system should quarantine it for review.
4. **Fahrenheit:** Convert every Fahrenheit reading using `C = (F - 32) × 5/9`. Store only Celsius in the cleaned readings table. This makes all station temperatures comparable.
5. **Formatting and invalid records:** Trim station names, validate dates and hours, and reject rows with invalid dates or hours. Convert numeric strings to numbers; unparseable text becomes missing and is handled by the missing-value rule.

### A2.2 Normalisation (2 marks)

For a PM2.5 value `x`:

**Min–max normalisation**

`x_scaled = (x - minimum) / (maximum - minimum)`

It maps the minimum to 0 and maximum to 1. It is useful when values need a common bounded range. If maximum equals minimum, return 0 for all values to avoid division by zero. It is sensitive to extreme values because the minimum and maximum determine the scale.

**Z-score standardisation**

`z = (x - mean) / standard_deviation`

It describes how many standard deviations a value is above or below the mean. It is useful when a method needs features centred around zero and measured on a comparable spread. If the standard deviation is zero, return 0 for every value. Calculate scaling parameters on the reference/training data and reuse them consistently.

### A2.3 Formatting (1 mark)

- Date: ISO format `YYYY-MM-DD`; hour: integer from 0 to 23.
- Station names: trim leading/trailing whitespace and use the station's canonical spelling (for example `Adyar`).
- Readings: numeric REAL values using a decimal point, with no unit text inside the value. Temperature is always Celsius after cleaning.
- Missing values: SQL NULL, not the strings `NA`, `None` or an empty string.

**Alternative: drop missing readings.** A single pass to identify and drop missing rows takes O(n) time; forward fill also takes O(n) after sorting. Dropping reduces stored rows and memory but may bias daily means if missing readings occur more often during sensor failures or pollution spikes. Computing a median by sorting valid values takes O(n log n) time and O(n) extra space in a straightforward implementation. Forward fill preserves the number of rows but may repeat an earlier value and smooth a sudden change.

**Algorithm A2 – Clean and normalise station readings**

Input: Raw station CSV rows. Output: Cleaned rows with standard units and formats.

BEGIN
1. Read the CSV header and records.
2. FOR each record DO
   - Trim and standardise the station name.
   - Validate the date and hour; reject invalid records.
   - Convert pollutant and temperature fields to numeric values; mark unparseable values as missing.
   - Mark pollutant values below 0 or above 999 as missing.
   - IF temperature unit is Fahrenheit THEN convert temperature to Celsius.
   - Check the `(station, date, hour)` key; skip duplicates and record the duplicate count.
3. Sort accepted records by station, date and hour.
4. FOR each station and each numeric measurement DO
   - Fill a missing value with the previous valid value, when available.
   - Otherwise use the station/measurement median, when available.
5. Format dates, hours, station names and numeric values consistently.
6. Return the cleaned records.
END

## A3 – Design the Analysis and Visualisation (5 marks)

### A3.1 Choose the charts (3 marks)

| Board question | Chart | Reason |
|---|---|---|
| Trend of PM2.5 over a month | Line chart | Dates are ordered time values; the line shows changes, peaks and direction over time. |
| Compare stations | Bar chart | Each station is a category; bar heights make station averages easy to compare. |
| Temperature vs PM2.5 | Scatter plot | Both measurements are numeric; points show association, clusters and outliers without implying a time order. |
| Hours with the worst air | Box plot grouped by hour | It compares the distribution and outliers for each hour. A histogram would show the overall distribution of PM2.5, not which hour is worst. |

### A3.2 Design the summary table (2 marks)

Create one row per station and date with columns: `station`, `date`, `pm25_min`, `pm25_max`, `pm25_mean`, and `valid_reading_count`. Use `MIN(pm25)`, `MAX(pm25)`, `AVG(pm25)` and `COUNT(pm25)` grouped by station and date. `COUNT(pm25)` ignores NULL values, so it counts valid PM2.5 measurements only.

Example SQL:

```sql
SELECT s.station_name, r.reading_date,
       MIN(r.pm25) AS pm25_min,
       MAX(r.pm25) AS pm25_max,
       AVG(r.pm25) AS pm25_mean,
       COUNT(r.pm25) AS valid_reading_count
FROM readings AS r
JOIN stations AS s ON s.station_id = r.station_id
GROUP BY s.station_name, r.reading_date;
```

**Alternative: Python loops.** Read rows and maintain a dictionary keyed by `(station, date)`. The straightforward version stores all PM2.5 values in a list for every key and calculates min, max, mean and count after reading; time is O(n) and storage for the lists is O(n). A running-sum/count/min/max dictionary also takes O(n) time but uses O(stations × days) aggregate storage. SQL `GROUP BY` scans the n rows and aggregates them in the database; sorting or temporary grouping structures may add overhead. SQL avoids transferring all raw readings into Python.

**Algorithm A3 – Produce daily summary and charts**

Input: Cleaned readings in SQLite. Output: Daily summary table and four labelled charts.

BEGIN
1. Execute a GROUP BY query on station and date.
2. Calculate minimum, maximum, mean and valid count for PM2.5.
3. Query daily mean PM2.5 by date; draw a line chart.
4. Query mean PM2.5 by station; draw a bar chart.
5. Query paired temperature and PM2.5 values; draw a scatter plot.
6. Group PM2.5 values by hour; draw a box plot.
7. Add a title and labelled axes to every chart; save the charts.
END

## A4 – Plan Debugging and Profiling (4 marks)

### A4.1 Debugging plan (2 marks)

- **Print statements:** During initial development, print a small sample of the raw row, converted values and cleaned row. This helps locate where an incorrect value enters the pipeline.
- **Assert statements:** Check program assumptions, for example `assert 0 <= hour <= 23`, `assert pm25 is None or pm25 >= 0`, and verify that no station/date/hour key is repeated after cleaning. Assertions catch logic errors early; they are not a replacement for input validation.
- **Logging:** Use `logging.info()` for progress, `logging.warning()` for rejected rows and `logging.error()` for failures. Include the source filename and row number. Set the logging level to WARNING or ERROR in production to hide routine messages without deleting the logging calls.
- **pdb / IDE debugger:** Put a breakpoint immediately before numeric conversion or imputation. Step through the problematic row and inspect local variables such as `station`, `raw_value`, `hour` and `previous_value`.

### A4.2 Profiling plan (2 marks)

- `time.perf_counter()` measures elapsed wall-clock time around a complete operation.
- `timeit` repeats a small operation many times and reports a more stable comparison. Use the same inputs and repetition count for both methods.
- `cProfile` records function calls and self/cumulative time. Sort by cumulative time to identify the functions taking the most total time, then optimise the largest cost first.

**Alternative: print for every debugging step.** Thousands of print calls cause terminal I/O and can slow a program substantially; the cost can hide the actual algorithm's performance. Logging can be filtered by its level, and inactive debugger breakpoints do not print every row. Print statements can be removed or guarded by a debug flag. Logging statements can remain in production with the level set to WARNING or ERROR. During timing, avoid verbose output so that the measurement focuses on the data-processing work.

**Algorithm A4 – Profile the cleaning program**

Input: Cleaning function and test dataset. Output: Elapsed time and profile report.

BEGIN
1. Record the start time using `time.perf_counter()`.
2. Run the cleaning function.
3. Record the end time and calculate elapsed time.
4. Use `timeit` to repeat the selected operation on the same input.
5. Enable `cProfile`, run the function and disable the profiler.
6. Sort the profile by cumulative time and save the report.
7. Identify the most expensive function and explain the result.
END

## A5 – Design an AI Application for Citizen Complaints (4 marks)

### A5.1 Sentiment and summary (2 marks)

**Lexicon sentiment scorer:** Store positive terms such as `{good, clean, fast, helpful, improved}` with score +1, and negative terms such as `{bad, dirty, slow, rude, smoke, broken}` with score −1. Tokenise the complaint into words. For each recognised word, reverse its score if the immediately preceding word is `not`, `never` or `no`. Add the scores. A positive total is positive, a negative total is negative and zero is neutral. This is simple and explainable, but it cannot reliably recognise sarcasm, unfamiliar words, long negation scope or mixed opinions.

**Extractive summariser:** Split the complaint into sentences, remove common stop words, count frequencies of important words across the text and score each sentence using the frequencies of the important words it contains. Select the highest-scoring sentences and return them in their original order. It selects original sentences rather than generating new ones.

**Algorithm A5.1 – Sentiment and extractive summary**

Input: Complaint text. Output: Sentiment label and short extractive summary.

BEGIN
1. Convert the text to lowercase and split it into words and sentences.
2. Set the sentiment total to zero.
3. FOR each word DO
   - Set its value to +1 if positive, −1 if negative, otherwise 0.
   - IF the preceding word is a negator THEN reverse the value.
   - Add the value to the total.
4. IF total is positive THEN label positive; ELSE IF total is negative THEN label negative; ELSE label neutral.
5. Remove stop words and count important-word frequencies.
6. Score each sentence using its important-word frequencies.
7. Select the top-scoring sentences and preserve their original order.
8. Return the label and summary.
END

### A5.2 Basic chatbot (2 marks)

1. Convert the question to lowercase.
2. Match a known station name such as Adyar or Guindy.
3. Identify intent words such as `PM2.5`, `today`, `average`, `maximum` or `minimum`.
4. Determine the requested date and execute a parameterised SQL query with `?` placeholders.
5. If the station or date is unclear, ask a follow-up question. If no record exists, report that no reading is available.

Example query:

```sql
SELECT AVG(r.pm25)
FROM readings AS r
JOIN stations AS s ON s.station_id = r.station_id
WHERE s.station_name = ? AND r.reading_date = ?;
```

Limitations: exact keyword matching may miss spelling errors and synonyms; station names may be ambiguous; the bot has little conversational memory; it does not understand sarcasm or complex language; and it cannot answer when the database has no matching reading.

**Algorithm A5.2 – Rule-based air-quality chatbot**

Input: Citizen question and SQLite database. Output: A text answer or clarification request.

BEGIN
1. Convert the question to lowercase.
2. Identify a station name from the known station list.
3. Identify the requested pollutant and date/intent from keywords.
4. IF station or date is missing THEN ask the citizen to clarify.
5. ELSE execute a parameterised SQL query using the station and date values.
6. IF a reading is returned THEN format and display the result.
7. ELSE display that no reading is available.
END

**Alternative: trained machine-learning model.** A Naive Bayes classifier learns word probabilities from labelled complaints. Prediction is generally related to the number of features present in the complaint, and the model stores word statistics for each class. A pre-trained language model can handle context and varied wording better, but requires much more memory and compute and can have higher response latency. A lexicon scorer uses very little memory and O(w) time for w words, but has limited accuracy. A trained model may improve accuracy only if it is evaluated on representative, correctly labelled local complaints. Compare precision, recall, accuracy, latency and memory before choosing it.
