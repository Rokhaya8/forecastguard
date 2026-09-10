from datetime import datetime

from airflow import DAG
import os
from airflow.providers.standard.operators.bash import BashOperator


PROJECT_DIR = "/opt/airflow/forecastguard"
DBT_DIR = f"{PROJECT_DIR}/dbt/forecastguard_dbt"


with DAG(
    dag_id="forecastguard_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["forecastguard"],
) as dag:

    ingest_orders = BashOperator(
        task_id="ingest_orders",
        bash_command=f"cd {PROJECT_DIR} && python -m src.ingestion.ingestion",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && dbt run --profiles-dir {DBT_DIR}",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && dbt test --profiles-dir {DBT_DIR}",
    )

    quality_check = BashOperator(
        task_id="quality_check",
        bash_command=f"cd {PROJECT_DIR} && python -m src.quality.volume_check",
    )

    forecast = BashOperator(
        task_id="forecast",
        bash_command=f"cd {PROJECT_DIR} && python -m src.forecasting.forecast",
    )

    assistant_diagnosis = BashOperator(
    task_id="assistant_diagnosis",
    bash_command=f"cd {PROJECT_DIR} && python -m src.assistant.diagnose",
    env={
        "DBT_RUN_STATUS": "SUCCESS",
        "DBT_TEST_STATUS": "SUCCESS",
        "QUALITY_CHECK_STATUS": "FAILED",
    },
    append_env=True,
    trigger_rule="all_failed",
)

    ingest_orders >> dbt_run >> dbt_test >> quality_check

    quality_check >> forecast
    quality_check >> assistant_diagnosis

