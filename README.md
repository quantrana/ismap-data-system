# Istanbul Shopping Mall Analytics Platform (ISMAP)

ISMAP is a cloud-native retail analytics platform that turns three years of shopping-mall transactions in Istanbul into a queryable star-schema warehouse on AWS. We ingest 99,458 raw retail transactions from a public Kaggle dataset, enrich them with Turkish public-holiday data from the Nager.Date API, and load the result into Amazon RDS PostgreSQL behind Streamlit and Tableau front-ends. The output answers practical questions for mall operators: which malls and categories drive revenue, how holidays and seasonality move the needle, who the highest-value customer segments are, and how payment behaviour differs by location.

## Architecture

The pipeline is intentionally simple: extract scripts pull data from external APIs and stage it in S3; an orchestration layer triggers a Glue ETL job that validates, transforms, and loads the data into a star schema in RDS PostgreSQL; CloudWatch monitors the runs; and the warehouse feeds both a Streamlit app for interactive exploration and Tableau for management reporting.

![Architecture](docs/architecture_diagram.png)

```
Kaggle API ──┐
             ├─► S3 (data lake) ──► Lambda ──► Glue ──► RDS PostgreSQL ──┬─► Streamlit
Nager.Date ──┘                                                          └─► Tableau
                                       │
                                       └─► CloudWatch (logs, metrics, alerts)
```

## Tech Stack

| Technology | Role | Why We Chose It |
| --- | --- | --- |
| Python 3.9+ | ETL, scripting, dashboard backend | Mature data ecosystem (`pandas`, `psycopg2`, `boto3`) |
| Amazon S3 | Data lake (raw, processed, rejected) | Cheap, durable, integrates with every other AWS service |
| AWS Lambda | Event-driven orchestration | Serverless triggers without standing up a scheduler |
| AWS Glue | Managed ETL runtime | Spark-based and pay-per-run; fits a bursty batch workload |
| Amazon RDS PostgreSQL | Analytics warehouse | Familiar SQL surface; great fit for a star schema |
| Amazon CloudWatch | Logs, metrics, alerts | Native to AWS; no extra monitoring stack to operate |
| Streamlit | Interactive analyst UI | Fastest path from a `pandas` DataFrame to a usable web page |
| Tableau | Executive reporting | Standard BI tool our stakeholders already use |
| Kaggle API | Source dataset extraction | Programmatic, reproducible downloads of the public dataset |
| Nager.Date API | Holiday enrichment | Free, well-documented public-holiday data for Turkey |

## Data Sources

- **Istanbul Shopping Mall dataset (Kaggle)** — 99,458 retail transactions across 10 Istanbul shopping malls, 2021–2023, 10 columns (invoice, customer, demographics, category, quantity, price, payment method, mall, date). [`kaggle.com/datasets/mehmettahiraslan/customer-shopping-dataset`](https://www.kaggle.com/datasets/mehmettahiraslan/customer-shopping-dataset)
- **Nager.Date Public Holidays API** — Turkish public holidays for 2021–2023, used to flag `is_holiday` on the time dimension. [`date.nager.at/Api`](https://date.nager.at/Api)

## Star Schema

A star schema keeps the analytical queries simple and fast: one fact table per grain joined directly to a small set of dimension tables. That structure suits our BI tools (Streamlit and Tableau both like flat joins), and it makes the SQL in `sql/sample_queries.sql` readable for non-engineers.

![Dimensional Model](docs/dimensional_model.png)

| Table | Description |
| --- | --- |
| `fact_sales` | One row per transaction (99,457 rows after validation) |
| `fact_daily_summary` | Pre-aggregated daily totals per store (7,963 rows) |
| `dim_time` | 797 dates enriched with 16 Turkish public holidays |
| `dim_customer` | 99,457 customers with derived age groups and lifecycle metrics |
| `dim_product` | 8 product categories |
| `dim_store` | 10 Istanbul shopping malls |
| `dim_payment` | 3 payment methods (Cash, Credit Card, Debit Card) |

## Getting Started

### Prerequisites

- Python 3.9 or newer
- An AWS account (the project fits comfortably inside the Free Tier)
- A PostgreSQL client (`psql` or DBeaver) for poking at the warehouse
- Git

### Setup

A teammate should be able to go from a fresh clone to a populated warehouse in about 15 minutes.

**1. Clone the repo**

```bash
git clone <repo-url> ismap
cd ismap
```

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**3. Configure your `.env`**

```bash
cp .env.example .env
```

Then fill in the values. AWS, RDS, and Kaggle credentials are **shared separately via the team channel** — they are deliberately not in the repo. The variables you need are listed in `.env.example`.

**4. Verify your environment**

```bash
python scripts/verify_setup.py
```

This runs 11 health checks (Python version, packages, `.env`, AWS, S3 bucket and folders, RDS reachability, schema, seeded dimensions, Kaggle, Nager.Date) and prints any required fix command.

**5. Bootstrap the database (first time only, or after a schema change)**

If the schema check failed in step 4:

```bash
python scripts/setup_database.py
```

This drops, recreates, verifies, and seeds the static dimensions (`dim_product`, `dim_store`, `dim_payment`).

**6. Pull the source data and run the pipeline**

```bash
# Download Kaggle dataset to data/raw/kaggle/ and stage it in S3
python scripts/extract_kaggle.py

# Fetch 2021–2023 Turkish holidays and stage them in S3
python scripts/extract_holidays.py

# Run the full ETL: validate → transform → load → verify
python etl/pipeline.py \
    --source local \
    --csv data/raw/kaggle/customer_shopping_data.csv \
    --holidays data/sample/holidays.json
```

**7. Re-run verification**

```bash
python scripts/verify_setup.py
```

You should now see `11/11 checks passed`.

### Running the Pipeline

Three useful modes:

```bash
# Dry run — validate + transform only, no DB writes (great for local iteration)
python etl/pipeline.py --source local \
    --csv data/sample/sample_100.csv \
    --holidays data/sample/holidays.json \
    --dry-run

# Local files, full load into RDS
python etl/pipeline.py --source local \
    --csv data/raw/kaggle/customer_shopping_data.csv \
    --holidays data/sample/holidays.json

# Read both inputs straight from S3 (production mode)
python etl/pipeline.py --source s3
```

Each run writes a timestamped log to `logs/pipeline_YYYYMMDD_HHMMSS.log` and saves any rejected rows to `data/sample/rejected_*.csv` (local) or `s3://<bucket>/rejected/` (S3).

## Project Structure

```
ismap/
├── config/              # Typed env-backed settings (config/settings.py)
├── scripts/             # Standalone CLI utilities
│   ├── extract_kaggle.py     # Kaggle download → validate → S3
│   ├── extract_holidays.py   # Nager.Date fetch → save → S3
│   ├── setup_database.py     # Drop / create / verify / seed RDS schema
│   └── verify_setup.py       # 11-point environment health check
├── etl/                 # Core ETL package
│   ├── pipeline.py           # Main entry point: read → validate → transform → load
│   ├── validate.py           # Schema and row-level data quality rules
│   ├── transform.py          # Build dimension and fact DataFrames
│   └── load.py               # Idempotent upserts into RDS PostgreSQL
├── lambda_functions/    # AWS Lambda handlers (orchestration, future phase)
├── sql/                 # DDL and reference analytical queries
├── dashboard/           # Streamlit app + per-tab pages
├── tests/               # Pytest suites for validate / transform / data quality
├── data/
│   ├── raw/             # Local cache of source files (gitignored)
│   └── sample/          # Small samples for local development and tests
├── docs/                # Architecture and dimensional model diagrams
├── logs/                # Pipeline run logs (gitignored)
├── .env.example         # Template — real .env is gitignored
└── requirements.txt
```

## Current Status

### Completed

- Project setup and configuration (`config/settings.py`, `.env` workflow, `verify_setup.py`)
- Data extraction from Kaggle and the Nager.Date API
- ETL pipeline: validate → transform → load → verify
- Star-schema warehouse (7 tables, fully populated and indexed)
- Idempotent database bootstrapper and seed data
- Pytest unit tests for validation and transformation

### In Progress / TODO

- AWS Lambda triggers wiring up `etl/pipeline.py` and `extract_*` scripts
- Amazon EventBridge schedules for nightly refreshes
- Amazon CloudWatch dashboards and alarms (failed runs, latency, row-count drift)
- Streamlit dashboard — 6 pages: Overview, Sales by Mall, Sales by Category, Time Trends, Customer Demographics, Payment Analysis
- Tableau workbooks pointed at RDS for executive reporting
- Expanded unit + integration test coverage
- Final report and presentation

## Contributing

A few simple conventions keep this repo easy to work in as a team:

- **Branching**: `feature/<your-name>-<short-description>` (for example, `feature/lan-streamlit-overview`).
- **Always pull `main` first.** Rebase or merge before pushing.
- **Run `python scripts/verify_setup.py`** before you start and after any infrastructure or schema change.
- **Run `pytest`** before opening a pull request.
- **Never commit `.env`, `kaggle.json`, or anything in `data/raw/`** — they are gitignored for a reason.
- **Open a pull request** for review before merging into `main`. Keep PRs small and focused.

## Team

| Name | Role | Responsibilities |
| --- | --- | --- |
| _TBD_ | Product owner | Scope, milestones, stakeholder communication |
| _TBD_ | Data engineer | ETL pipeline, AWS infrastructure, schema |
| _TBD_ | Data engineer | Lambda orchestration, CloudWatch monitoring |
| _TBD_ | BI / analytics | Streamlit dashboard, Tableau workbooks |
| _TBD_ | QA / docs | Tests, documentation, final presentation |

## License

Released under the **MIT License**. Copyright (c) 2026 ISMAP contributors.

```
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
