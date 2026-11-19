# CSA08-1924260076-Assignment5

**Student:** Prajeesh B.  
**Register Number:** 1924260076  
**Course Outcome:** CO5 – Data Acquisition, Cleaning, Analysis and AI Applications

## Software and libraries
- Python 3.12 or later (the prepared scripts were checked with Python 3.13.5)
- pandas 2.2.3
- matplotlib 3.10.8

## Task folders and run commands
Run commands from this repository's root folder in the VS Code terminal.

| Folder | Run command | What it does |
|---|---|---|
| `TaskB1` | `python TaskB1/task_b1.py` | Shows before/after cleaning, stores clean data in SQLite, runs three SQL questions and creates four charts, and measures CSV-vs-pandas cleaning at 1k, 100k and 1m rows. |
| `TaskB1` | `python TaskB1/complete_code_b1.py` | Executes the two completed TODOs and the added PM2.5 > 999 test. |
| `TaskB2` | `python TaskB2/task_b2.py` | Tests malformed files, SQL injection, quoted station names and sentiment edge cases. |
| `TaskB2` | `python TaskB2/complete_code_b2.py` | Executes the two completed SQLite TODOs. |
| `TaskB3` | `python TaskB3/task_b3.py` | Compares CSV loops, pandas and SQL for 1, 12 and 120 stations; checks correctness and profiles the CSV-loop method. |
| `TaskB4` | `python TaskB4/complete_code_b4.py` | Executes the completed sentiment-scoring TODO with the assignment test sentences. |
| `TaskB4` | `python TaskB4/task_b4.py` | Scores 50 complaints, compares two summaries, prompts you to complete your own manual labels, and measures a composite SQL index. |

## Data and outputs
- `TaskB2/data/`: malformed CSV, wrong-delimiter, UTF-16 and empty-file test inputs.
- `TaskB1/data/cleaning_edge_cases.csv`: small input designed to exercise missing values, invalid numeric values, duplicate keys, Fahrenheit conversion, inconsistent station spelling and invalid date/hour rows.
- `TaskB1/data/station_readings_october.csv`: deterministic 12-station, hourly October dataset used for analysis and charts.
- `TaskB4/data/complaints.csv`: 50 example citizen complaints.
- `TaskB4/data/manual_complaint_labels.csv`: fill the `your_label` column after reading each complaint yourself; then rerun B4 to calculate your agreement. Do not claim an agreement percentage before completing this.
- `outputs/`: generated SQLite database, cleaned CSV files, charts, SQL summaries, timing results and profiling output.


