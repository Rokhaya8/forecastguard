# ForecastGuard

**Reliable Sales Forecasting Pipeline**

ForecastGuard is an end-to-end data pipeline designed to ensure that a
forecasting model only runs when the data feeding it is reliable.

A forecasting model can execute successfully while still producing unreliable
predictions if upstream data is incomplete or inconsistent. ForecastGuard
addresses this problem by validating transformed sales data before allowing
the forecasting step to run.

When a data quality anomaly is detected, the forecast is blocked and an LLM
assistant analyzes the available pipeline context to explain the anomaly and
suggest relevant investigation steps.

## Architecture

```text
Synthetic Orders
      |
      v
   Airflow
      |
      v
 PostgreSQL
      |
      v
     dbt
      |
      v
Data Quality Check
    /       \
 PASS       FAIL
  |           |
  v           v
Forecast    LLM Assistant
```

## Tech Stack

- **Python** — ingestion, data quality, forecasting and anomaly simulation
- **Apache Airflow** — pipeline orchestration
- **PostgreSQL** — data storage
- **dbt Core** — SQL transformations and structural data tests
- **Gemini API** — contextual anomaly explanation
- **Docker** — reproducible local infrastructure

## Data Quality Scenario

ForecastGuard includes a simulated low-volume anomaly to demonstrate how the
pipeline reacts to unreliable input data.

Under normal conditions, the synthetic dataset contains approximately
900–1,100 orders per day. The pipeline compares the latest daily order volume
with the average volume of the previous seven days.

For the anomaly scenario, only **150 orders** are generated for a new day,
while the previous 7-day average is approximately **1,040 orders**.

```text
Latest daily volume : 150 orders
7-day average       : ~1,040 orders
Volume ratio        : ~14.4%
Quality threshold   : 70%
```

Because the volume ratio falls below the quality threshold:

```text
dbt tests            → PASSED
volume quality check → FAILED
forecast             → BLOCKED
LLM diagnosis        → TRIGGERED
```

This illustrates an important distinction: structural tests can pass while the
data is still unsuitable for downstream analytical or ML workloads.

## How It Works

The pipeline is orchestrated by Airflow and follows a sequence of validation
steps before producing a forecast.

### 1. Data Ingestion

A Python script generates synthetic sales orders and loads them into the
`raw_orders` table in PostgreSQL.

### 2. Data Transformation

dbt transforms the raw data into analytical models:

- `stg_orders` enriches individual orders with calculated sales amounts.
- `fct_daily_sales` aggregates orders into daily sales metrics.

dbt tests validate structural properties such as non-null values and unique
order identifiers.

### 3. Data Quality Gate

A Python quality check compares the latest order volume with the previous
7-day average.

If the volume is above the defined threshold, the pipeline continues.
If it falls below the threshold, the quality task fails.

### 4. Forecasting

When data quality checks pass, ForecastGuard generates a simple 7-day
moving-average forecast for the next day's order volume.

The forecasting method is intentionally simple: the focus of the project is
the reliability of the data pipeline feeding the model.

### 5. LLM-Assisted Diagnosis

When the volume quality check fails, the forecasting task is blocked and an
LLM assistant is triggered.

The assistant receives the available pipeline and quality context, separates
observed facts from plausible hypotheses, and recommends investigation steps
based only on the available data.

## Run Locally

### Prerequisites

Make sure the following tools are installed:

- Docker Desktop
- Python 3.10+
- Git

### 1. Clone the repository

```bash
git clone <https://github.com/Rokhaya8/forecastguard.git>
cd forecastguard
```

### 2. Configure environment variables

Create a `.env` file based on `.env.example`.

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then add your own Gemini API key to `.env`.

> Never commit the `.env` file. It is excluded through `.gitignore`.

### 3. Install local Python dependencies

Create a virtual environment:

```bash
python -m venv .venv
```

On Windows PowerShell, activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 4. Generate the synthetic dataset

```bash
python -m src.simulation.generate_data
```

This generates:

```text
data/orders.csv
```

The generated dataset is intentionally excluded from Git because it can be
reproduced locally from the simulation script.

### 5. Start the infrastructure

```bash
docker compose up -d
```

Docker starts the PostgreSQL database and the Airflow environment.

The Airflow UI is available at:

```text
http://localhost:8081
```

### 6. Run the normal pipeline

Trigger the `forecastguard_pipeline` DAG from the Airflow UI.

Expected result:

```text
ingest_orders   → SUCCESS
dbt_run         → SUCCESS
dbt_test        → SUCCESS
quality_check   → SUCCESS
forecast        → SUCCESS
```

### 7. Simulate a data quality anomaly

Run:

```bash
python -m src.simulation.simulate_anomaly
```

Then trigger the Airflow DAG again.

Expected result:

```text
ingest_orders        → SUCCESS
dbt_run              → SUCCESS
dbt_test             → SUCCESS
quality_check        → FAILED
forecast             → BLOCKED
assistant_diagnosis  → SUCCESS
```

The LLM assistant analyzes the detected anomaly and recommends relevant
investigation steps.

## Project Structure

```text
forecastguard/
├── airflow/
│   └── dags/
│       └── forecastguard_pipeline.py
├── dbt/
│   └── forecastguard_dbt/
│       ├── models/
│       │   ├── staging/
│       │   └── marts/
│       ├── dbt_project.yml
│       └── profiles.yml
├── src/
│   ├── ingestion/
│   ├── quality/
│   ├── forecasting/
│   ├── assistant/
│   └── simulation/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile.airflow
├── requirements.txt
└── requirements-airflow.txt
```

## Roadmap

ForecastGuard currently focuses on a reproducible local pipeline and a
single volume-based data quality scenario.

Possible future improvements include:

- additional quality checks for freshness, duplicates and schema changes
- richer historical monitoring of data quality metrics
- retrieval of runbooks and previous incidents to enrich LLM context
- tool-using AI capabilities for deeper pipeline investigation
- controlled remediation actions with validation and human approval
- cloud warehouse deployment and CI/CD
