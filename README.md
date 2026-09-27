# ForecastGuard

**A sales forecasting pipeline that refuses to publish a forecast built on unreliable data.**

ForecastGuard checks the data feeding a forecast before the forecast is
produced. When the data looks normal, the forecast is published. When it
doesn't, the forecast is blocked, the incident is recorded, and an LLM
assistant explains what may have gone wrong and what to check.

## The problem

A forecasting pipeline can run without a single error and still produce a
wrong number.

Imagine a retailer that uses a daily sales forecast to decide how much stock
to order. One morning, only part of the previous day's orders reach the
database: an export failed, or a source arrived late. Every step of the
pipeline still succeeds. The model sees a sharp drop in sales, predicts a
weak day, and the purchasing team orders less. Two weeks later, the shelves
are empty.

Nothing crashed, so nobody noticed. That is the dangerous case: a wrong
forecast presented as a correct one is worse than no forecast at all.

Classic data tests do not catch this. They check the **shape** of the data
(no missing values, no duplicate orders), not whether there is **enough** of
it. A partially loaded day passes every structural test.

## What ForecastGuard does

1. **Loads and transforms the sales data**, then runs structural tests.
2. **Checks the volume of the latest day** against the average of the 7
   previous days. Below 70%, the data is considered unreliable.
3. **Decides what happens next:**
   - volume is normal → the forecast is produced and published;
   - volume is abnormal → the forecast is blocked and the incident is
     diagnosed.
4. **Records every decision** in a `forecast_runs` table: what data was
   checked, the figures, the decision, and the forecast or the diagnosis.
5. **Shows the result in a dashboard** answering one question: can today's
   forecast be trusted, and if not, why?

When a forecast is blocked, the LLM assistant (Gemini) receives the figures
of the incident and returns a short diagnosis that separates observed facts
from hypotheses, and recommends checks based only on the data that exists.
It proposes; a human decides.

## Why I built it

While working on sales forecasting with LSTM models, I studied how the
volume of training data affected the reliability of the predictions. The
main lesson was that the model was rarely the weak point: the data feeding
it was.

ForecastGuard is built around that lesson. The forecasting model is
intentionally simple (a 7-day moving average), because the project is not
about predicting better. It is about making sure a prediction deserves to be
trusted before anyone acts on it.

## Architecture

```text
Synthetic orders (CSV)
        │
        ▼
  ingest_orders ──► PostgreSQL (raw_orders)
        │
        ▼
     dbt run ──────► stg_orders, fct_daily_sales
        │
        ▼
     dbt test        structural tests (not null, unique)
        │
        ▼
  quality_check      volume vs. 7-day average
     /      \
 normal    abnormal
   │          │
   ▼          ▼
forecast   assistant_diagnosis (Gemini)
   │          │
   └────┬─────┘
        ▼
  forecast_runs table ──► Streamlit dashboard
```

The whole pipeline is orchestrated by Airflow. `quality_check` is a branch:
it measures the data, then chooses the next task itself. A blocked forecast
is therefore a **successful** pipeline run, because the system did its job.
Only a real technical failure (database unreachable, broken transformation)
appears as a failed run in Airflow.

## Tech stack

- **Python**: ingestion, volume check, forecast, diagnosis, data simulation
- **Apache Airflow**: orchestration and branching
- **PostgreSQL**: storage of raw data, models and run history
- **dbt Core**: SQL transformations and structural tests
- **Gemini API**: incident diagnosis
- **Streamlit**: monitoring dashboard
- **Docker Compose**: the full stack starts with one command

## Run it locally

### Prerequisites

- Docker Desktop
- Python 3.10+
- Git
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone the repository

```bash
git clone https://github.com/Rokhaya8/forecastguard.git
cd forecastguard
```

### 2. Configure the environment

Create a `.env` file from the template:

```powershell
Copy-Item .env.example .env
```

Then replace `GEMINI_API_KEY` in `.env` with your own key. The other values
can stay as they are.

> The `.env` file is excluded by `.gitignore`. Never commit it.

### 3. Install the local Python dependencies

These are only used to generate the data from your terminal.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Start the stack

```bash
docker compose up -d --build
```

This starts three containers:

| Container                 | Role                   | Address               |
| ------------------------- | ---------------------- | --------------------- |
| `forecastguard-postgres`  | Database               | `localhost:5433`      |
| `forecastguard-airflow`   | Pipeline orchestration | http://localhost:8081 |
| `forecastguard-dashboard` | Monitoring dashboard   | http://localhost:8501 |

Airflow generates a password for the `admin` user each time its container is
created. To read it:

```bash
docker exec forecastguard-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

### 5. Run the normal scenario

```bash
python -m src.simulation.generate_data
```

This creates 45 days of synthetic orders (about 1,000 per day) in
`data/orders.csv`. Then trigger the `forecastguard_pipeline` DAG in Airflow.

Expected result:

```text
ingest_orders        → success
dbt_run              → success
dbt_test             → success
quality_check        → success (routes to forecast)
forecast             → success
assistant_diagnosis  → skipped
```

The dashboard shows a published forecast.

### 6. Run the anomaly scenario

```bash
python -m src.simulation.simulate_anomaly
```

This adds a new day with only 150 orders, against a usual volume of about
1,040. Trigger the DAG again.

Expected result:

```text
ingest_orders        → success
dbt_run              → success
dbt_test             → success   (the data is well formed...)
quality_check        → success   (...but too small: routes to diagnosis)
forecast             → skipped
assistant_diagnosis  → success
```

The dashboard shows a blocked forecast, the volume drop on the chart, and
the diagnosis. To go back to normal data, run `generate_data` again.

### 7. Inspect the run history

```bash
docker exec forecastguard-postgres psql -U forecastguard -d forecastguard -c "SELECT id, data_date, current_orders, volume_ratio, status, predicted_orders FROM forecast_runs;"
```

## Project structure

```text
forecastguard/
├── airflow/
│   └── dags/
│       └── forecastguard_pipeline.py   # DAG with the quality branch
├── dashboard/
│   └── app.py                          # Streamlit dashboard
├── dbt/
│   └── forecastguard_dbt/
│       ├── models/
│       │   ├── staging/                # source + stg_orders
│       │   ├── marts/                  # fct_daily_sales
│       │   └── schema.yml              # structural tests
│       ├── dbt_project.yml
│       └── profiles.yml
├── src/
│   ├── ingestion/                      # CSV → raw_orders
│   ├── quality/                        # volume check
│   ├── forecasting/                    # 7-day moving average
│   ├── assistant/                      # Gemini diagnosis
│   ├── storage/                        # forecast_runs table
│   └── simulation/                     # normal and anomaly data
├── .env.example
├── docker-compose.yml
├── Dockerfile.airflow
├── Dockerfile.streamlit
├── requirements.txt
├── requirements-airflow.txt
└── requirements-dashboard.txt
```

## Limitations and next steps

ForecastGuard is a local, single-scenario project. Its current limits, and
what would come next in a production setting:

- **One quality check.** Only daily volume is checked. Next: freshness,
  duplicates, and volume per product or per store.
- **Full refresh ingestion.** All orders are reloaded on every run. With real
  volumes, loading would be incremental.
- **Manual trigger.** The DAG has no schedule. Next: a daily schedule and an
  alert (email or Slack) when a forecast is blocked.
- **Local Airflow.** `airflow standalone` keeps its metadata inside the
  container, so run history in the Airflow UI is lost when the container is
  recreated. The `forecast_runs` table is not affected.
- **Credentials.** The dbt profile contains the database password. It should
  read it from environment variables instead.
- **Richer diagnosis.** Give the assistant past incidents and runbooks as
  context, and let it run read-only queries to test its own hypotheses.
