# Contributing to ISMAP

Hi team. This document is your guide and your task brief — read it once end-to-end, then keep it open while you work.

It covers three things:

1. **Getting set up** so you can run the pipeline locally 
2. **Your role and tasks**,
3. **Our git workflow and house rules** 

If anything here is unclear or feels wrong, flag it in the team channel. This guide is meant to evolve.

---

## Getting Started for New Contributors

You'll need: **Python 3.9+**, **Git**, a **PostgreSQL client** (`psql` or DBeaver), and access to the team's AWS account (ask the team lead).

### 1. Clone the repo

```bash
git clone <repo-url> ismap
cd ismap
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Keep your venv activated for everything below. If you open a new terminal, re-run `source venv/bin/activate`.

### 3. Get your `.env` from the team channel

```bash
cp .env.example .env
```

The real AWS, RDS, and Kaggle credentials are pinned in our team channel — copy them into `.env`. **Don't commit this file.** It's already in `.gitignore`.

### 4. Verify your setup

```bash
python scripts/verify_setup.py
```

This runs 11 health checks (Python, packages, `.env`, AWS, S3, RDS, schema, seeded dimensions, Kaggle, Nager.Date). If anything fails, the script prints the exact fix command. Don't move on until you see `11/11 checks passed`.

### 5. Run a pipeline dry-run

```bash
python etl/pipeline.py \
    --source local \
    --csv data/sample/sample_100.csv \
    --holidays data/sample/holidays.json \
    --dry-run
```

This validates and transforms the 100-row sample without touching the database. If it exits cleanly, you're ready to start contributing.

---

## Team Roles and Task Allocation

Each teammate owns one branch and one slice of the system. Work in your slice unless you've cleared a cross-cutting change with the rest of the team.

### Teammate A — Lambda & Orchestration Engineer - Michael

**Your job:** automate the ETL pipeline so it runs without manual intervention.

When you're done, uploading a CSV to S3 should kick off the entire pipeline by itself, and the holiday data should refresh on a schedule with zero human input.

**Tasks (in order):**

1. **Get familiar with Lambda (~1–2 hours).** Skim the official getting-started guide: <https://docs.aws.amazon.com/lambda/latest/dg/getting-started.html>. Focus on the handler signature, the event payload, and how to package dependencies.

2. **Implement `lambda_functions/trigger_glue.py`.** It should be a Lambda handler that:
   - Receives an S3 event.
   - Parses the bucket name and the object key from `event["Records"][0]["s3"]`.
   - Only proceeds if the key is a `.csv` file under the `raw/` prefix; otherwise log and return.
   - Starts the Glue ETL job. Until Glue is wired up, simulate it by invoking our local pipeline (`etl.pipeline.run_pipeline(source="s3")`) and log the outcome.
   - Logs every branch with `logging.getLogger(__name__)` — no `print`.

3. **Wire up the S3 event notification** in the AWS console so any object landing in `s3://<bucket>/raw/kaggle/` triggers your Lambda. Document the IAM role and trust policy you used.

4. **Implement `lambda_functions/extract_holidays_lambda.py`.** Same logic as `scripts/extract_holidays.py` but as a Lambda handler. Default to fetching the current year, but accept `start_year` and `end_year` overrides from the event payload.

5. **Set up an EventBridge rule** that runs the holidays Lambda once a week (Sunday, 02:00 UTC works fine). Name the rule `ismap-holidays-weekly`.

6. **Test end-to-end:** drop a fresh CSV into `s3://<bucket>/raw/kaggle/`, watch your Lambda fire in CloudWatch Logs, confirm the warehouse rows update.

**Testing locally before deploying:**

You can invoke a Lambda handler directly from Python with a fake event. Create the fixture once:

```bash
mkdir -p tests/fixtures
```

Put a sample S3 event JSON at `tests/fixtures/s3_event_sample.json`, then run:

```python
import json
from lambda_functions import trigger_glue

with open("tests/fixtures/s3_event_sample.json") as f:
    event = json.load(f)

trigger_glue.lambda_handler(event, None)
```

**Files you'll touch:**

- `lambda_functions/trigger_glue.py`
- `lambda_functions/extract_holidays_lambda.py`
- `tests/fixtures/` (new — share fixtures with Teammate D)
- `config/settings.py` (only if you genuinely need new env vars; clear it with the team first)

**Branch name:** `feature/lambda-orchestration`

---

### Teammate B — Monitoring & Alerting Engineer

**Your job:** set up CloudWatch and SNS so we hear about failures before our users do.

**Tasks (in order):**

1. **Get familiar with CloudWatch (~1 hour):** <https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/GettingStarted.html>. Focus on metrics, alarms, and log groups.

2. **Get familiar with SNS (~30 min):** <https://docs.aws.amazon.com/sns/latest/dg/welcome.html>. You only need topics and email subscriptions for now.

3. **Create the SNS topic `ismap-alerts`** and subscribe each teammate's email. Confirm every subscription before moving on.

4. **Alarm: pipeline failures.** Trigger when the ETL pipeline log records an `ERROR`-level event, or when the run exit code is non-zero. Action: publish to `ismap-alerts`.

5. **Alarm: Lambda errors.** One alarm per Lambda function (`trigger_glue`, `extract_holidays_lambda`). Threshold: `Errors > 0` over 5 minutes. Action: publish to `ismap-alerts`.

6. **Build a CloudWatch dashboard** named `ISMAP Operations` with at least:
   - Pipeline run status over the last 7 days (success vs failure count).
   - Lambda invocation counts and error counts.
   - RDS CPU utilisation and active connection count.

7. **Automate the setup in `scripts/setup_monitoring.py`.** Use `boto3` (CloudWatch + SNS clients) so the entire monitoring stack can be recreated by running:

   ```bash
   python scripts/setup_monitoring.py
   ```

   The script must be **idempotent** — running it twice shouldn't create duplicate alarms or topics.

8. **Document the setup** in `docs/monitoring.md`: what each alarm watches, who gets paged, how to silence an alarm during planned maintenance, and how to add a new subscriber.

**Files you'll touch:**

- `scripts/setup_monitoring.py` (new)
- `docs/monitoring.md` (new)

**Branch name:** `feature/cloudwatch-monitoring`

---

### Teammate C — Dashboard Developer

**Your job:** build the Streamlit dashboard and a small set of Tableau visualisations.

**Tasks (in order):**

1. **Get familiar with Streamlit (~2 hours):** <https://docs.streamlit.io/get-started>. Focus on `st.sidebar`, `st.metric`, page-based navigation, and `@st.cache_data`.

2. **Connect Streamlit to PostgreSQL.** Use `psycopg2` for the connection and `pandas.read_sql_query` for the data. One connection helper for the whole app — don't open a new connection per page.

3. **Configure secrets.** Copy `dashboard/.streamlit/secrets.toml.example` to `dashboard/.streamlit/secrets.toml` and fill in the RDS values from `.env`. **Do not commit `secrets.toml`** — confirm it's gitignored before your first push.

4. **Build `dashboard/app.py`** as the entry point with sidebar navigation across the six pages. Add a small "About" section in the sidebar explaining the data window (2021–2023, 10 Istanbul malls).

5. **Build the six pages, one at a time.** Test each in isolation before starting the next. Use `plotly.express` for every chart — it looks more polished than `st.bar_chart` and gives users hover/zoom for free.

   - **Page 1 — Overview** (`dashboard/pages/01_overview.py`)
     - Four KPI cards: Total Revenue, Total Transactions, Unique Customers, Avg Transaction Value.
     - Monthly revenue trend (line chart).
     - Revenue by mall (bar chart).
   - **Page 2 — Sales by Mall** (`dashboard/pages/02_sales_by_mall.py`)
     - Mall selector dropdown.
     - Revenue comparison across malls (bar chart).
     - Detailed metrics table per selected mall.
   - **Page 3 — Sales by Category** (`dashboard/pages/03_sales_by_category.py`)
     - Revenue share by category (pie chart).
     - Quantity sold by category (bar chart).
   - **Page 4 — Time Trends** (`dashboard/pages/04_time_trends.py`)
     - Monthly and quarterly revenue trends.
     - Holiday vs non-holiday comparison.
     - Weekend vs weekday comparison.
     - Seasonal breakdown.
   - **Page 5 — Customer Demographics** (`dashboard/pages/05_customer_demographics.py`)
     - Age group distribution.
     - Gender split.
     - Spending heatmap by age group × gender.
   - **Page 6 — Payment Analysis** (`dashboard/pages/06_payment_analysis.py`)
     - Payment method distribution.
     - Payment method by mall.

6. **Cache every database query** with `@st.cache_data(ttl=600)`. The warehouse data only changes when ETL runs, so a 10-minute cache is plenty and dramatically reduces load on RDS.

7. **Tableau visualisations.** Once Streamlit is in good shape, connect Tableau to RDS PostgreSQL and build four workbook views:
   - Revenue heatmap by mall × month.
   - Category performance comparison.
   - Holiday impact analysis.
   - Customer demographic patterns.

**How to run the dashboard locally:**

```bash
streamlit run dashboard/app.py
```

**How to develop SQL fast:** prototype each query in `psql` or DBeaver first, copy it from `sql/sample_queries.sql` as a starting point, and only port it into the dashboard once it returns the right shape of data.

**Files you'll touch:**

- `dashboard/app.py`
- `dashboard/pages/*.py`
- `dashboard/.streamlit/secrets.toml` (local only — never commit)

**Branch name:** `feature/streamlit-dashboard`

---

### Teammate D — Testing & Quality Assurance

**Your job:** prove the pipeline does what it says, and keep the codebase honest with reviews.

**Tasks (in order):**

1. **Get familiar with pytest (~1 hour):** <https://docs.pytest.org/en/stable/getting-started.html>. Focus on fixtures, `parametrize`, and markers.

2. **Build `tests/conftest.py` with shared fixtures.** At minimum: a small valid retail DataFrame, a small invalid retail DataFrame, and a holidays list with one known Turkish holiday.

3. **Expand `tests/test_validate.py`** to cover:
   - Valid data passes validation.
   - Missing columns are caught.
   - An invalid category (e.g. `"Electronics"`) is rejected.
   - Negative `quantity` is rejected.
   - Negative `price` is rejected.
   - Null `invoice_no` is rejected.
   - Mixed valid/invalid rows are split correctly by `separate_valid_invalid`.

4. **Expand `tests/test_transform.py`** to cover:
   - `parse_invoice_date("5/8/2022")` returns `2022-08-05` (day-first).
   - `_age_group(25) == "18-25"`, `_age_group(30) == "26-35"`.
   - `fact_sales.total_amount == quantity * price` for every row.
   - `dim_time.is_holiday` is `True` for a known Turkish holiday (e.g. 23 April).
   - `dim_time.is_weekend` is `True` for a Saturday and a Sunday.
   - `dim_time.season` is `"Spring"` for March, `"Summer"` for July.

5. **Build `tests/test_data_quality.py` as integration tests** that run against the actual warehouse:
   - `fact_sales` row count ≈ 99,457 (allow a small tolerance for rejected rows).
   - Every `fact_sales` foreign key resolves to a row in its dimension.
   - No null surrogate keys anywhere in `fact_sales`.
   - For a random sample of `fact_sales`, `total_amount == quantity * price`.
   - `dim_store` has 10 rows, `dim_product` has 8, `dim_payment` has 3.
   - `dim_time` contains at least one row with `is_holiday = TRUE`.

   Mark every test in this file with `@pytest.mark.integration` so they only run when explicitly requested.

6. **Run the suites:**

   ```bash
   pytest tests/ -v                          # everything
   pytest tests/ -m "not integration" -v     # unit tests only (CI)
   pytest tests/ -m integration -v           # DB integration tests only
   ```

   Register the marker in `pytest.ini` or `pyproject.toml` so pytest doesn't warn about it.

7. **Review the existing codebase.** Read every module in `etl/` and `scripts/`, file PR comments for any bugs, weak error handling, or unclear logic you find. Quality issues you can't fix yourself in this branch should be opened as GitHub issues.

**Files you'll touch:**

- `tests/conftest.py` (new)
- `tests/test_validate.py`
- `tests/test_transform.py`
- `tests/test_data_quality.py`

**Branch name:** `feature/test-suite`

---

## Git Workflow

We use a feature-branch + pull-request flow. Nothing fancy.

**1. Always start from an up-to-date `main`:**

```bash
git checkout main
git pull origin main
```

**2. Cut a feature branch:**

```bash
git checkout -b feature/your-branch-name
```

**3. Commit small and often** with descriptive messages:

```bash
git add path/to/file
git commit -m "feat: implement overview dashboard page with KPI cards"
```

**4. Push your branch:**

```bash
git push -u origin feature/your-branch-name
```

**5. Open a Pull Request on GitHub.**

- Describe what you did and why.
- Link any related issues.
- Tag the team lead for review.
- Keep PRs small — easier to review, faster to merge.

**6. Address review comments**, then merge into `main` once approved. Delete the branch after merging.

### Commit message prefixes

| Prefix | Use for |
| --- | --- |
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `test:` | Adding or updating tests |
| `refactor:` | Code cleanup, no behaviour change |
| `chore:` | Tooling, configuration, dependencies |

---

## Important Rules

A few things to internalise — most of them save you (or someone else) from a really bad afternoon.

- **Never commit `.env`, `secrets.toml`, `kaggle.json`, or anything else with credentials.** If you do this by accident, rotate those credentials immediately and tell the team.
- **Never push directly to `main`.** Always use a branch and a pull request, even for one-line fixes.
- **Run `python scripts/verify_setup.py` before you push.** It catches most "works on my machine" surprises.
- **Run `pytest -m "not integration"` before you push.** Unit tests must stay green at all times.
