from datetime import datetime

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import BranchPythonOperator


PROJECT_DIR = "/opt/airflow/forecastguard"
DBT_DIR = f"{PROJECT_DIR}/dbt/forecastguard_dbt"


def choose_next_step():
    import sys

    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)

    from src.quality.volume_check import evaluate_volume

    metrics = evaluate_volume()

    if metrics["passed"]:
        return "forecast"

    return "assistant_diagnosis"


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

    quality_check = BranchPythonOperator(
        task_id="quality_check",
        python_callable=choose_next_step,
    )

    forecast = BashOperator(
        task_id="forecast",
        bash_command=f"cd {PROJECT_DIR} && python -m src.forecasting.forecast",
    )

    assistant_diagnosis = BashOperator(
        task_id="assistant_diagnosis",
        bash_command=f"cd {PROJECT_DIR} && python -m src.assistant.diagnose",
    )

    ingest_orders >> dbt_run >> dbt_test >> quality_check

    quality_check >> [forecast, assistant_diagnosis]