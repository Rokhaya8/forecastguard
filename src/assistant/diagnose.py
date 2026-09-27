import os
import time 

import psycopg
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from src.storage.runs import save_run

load_dotenv()

MODEL_NAME = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 20

def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_latest_quality_context(connection):
    query = """
        WITH daily_sales AS (
            SELECT
                order_date,
                number_of_orders
            FROM analytics.fct_daily_sales
        ),
        latest_day AS (
            SELECT MAX(order_date) AS latest_date
            FROM daily_sales
        )
        SELECT
            latest.order_date,
            latest.number_of_orders,
            AVG(history.number_of_orders) AS historical_average
        FROM daily_sales latest
        CROSS JOIN latest_day
        JOIN daily_sales history
            ON history.order_date < latest_day.latest_date
           AND history.order_date >= latest_day.latest_date - INTERVAL '7 days'
        WHERE latest.order_date = latest_day.latest_date
        GROUP BY
            latest.order_date,
            latest.number_of_orders;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchone()


def build_diagnostic_context():
    with get_connection() as connection:
        result = get_latest_quality_context(connection)

    if result is None:
        raise RuntimeError("Not enough data to build diagnostic context.")

    order_date, current_volume, historical_average = result
    historical_average = float(historical_average)
    volume_ratio = current_volume / historical_average

    return {
        "pipeline": "ForecastGuard",
        "dbt_run": os.getenv("DBT_RUN_STATUS", "UNKNOWN"),
        "dbt_test": os.getenv("DBT_TEST_STATUS", "UNKNOWN"),
        "latest_date": order_date,
        "current_orders": current_volume,
        "historical_average_7d": round(historical_average, 2),
        "volume_ratio": round(volume_ratio, 4),
        "quality_check": os.getenv(
            "QUALITY_CHECK_STATUS",
            "FAILED" if volume_ratio < 0.70 else "PASSED"
      ),
        "forecast_status": "BLOCKED" if volume_ratio < 0.70 else "READY",
    }


def build_prompt(context):
    return f"""
You are a data reliability assistant.

Analyze only the evidence provided below.

Pipeline context:
- Pipeline: {context["pipeline"]}
- dbt run: {context["dbt_run"]}
- dbt test: {context["dbt_test"]}
- Latest date: {context["latest_date"]}
- Current orders: {context["current_orders"]}
- 7-day historical average: {context["historical_average_7d"]}
- Volume ratio: {context["volume_ratio"]:.2%}
- Quality check: {context["quality_check"]}
- Forecast status: {context["forecast_status"]}

Available data fields:
- order_id
- customer_id
- product_id
- order_date
- quantity
- unit_price
- total_amount
- number_of_orders
- total_quantity
- total_revenue
- avg_order_value

Instructions:
- Explain the anomaly clearly.
- Give 2 or 3 plausible causes.
- Separate facts from hypotheses.
- Do not claim certainty without evidence.
- Do not invent columns, timestamps, APIs, services, logs, or upstream systems that are not listed.
- Recommend only checks that can be performed using the available data or the pipeline components explicitly mentioned.
- Keep the answer concise.
"""


def get_llm_diagnosis(context):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the environment.")

    client = genai.Client(api_key=api_key)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=build_prompt(context),
            )
            return response.text

        except errors.APIError as error:
            print(
                f"Gemini call failed (attempt {attempt}/{MAX_ATTEMPTS}): "
                f"{error.code} {error.message}"
            )

            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)

    return None

def main():
    context = build_diagnostic_context()

    print("Diagnostic context")
    print("------------------")

    for key, value in context.items():
        print(f"{key}: {value}")

    print("\nLLM diagnosis")
    print("-------------")

    diagnosis = get_llm_diagnosis(context)
    if diagnosis is None:
        print(
            "Diagnosis unavailable: Gemini did not respond. "
            "The incident details above remain valid."
        )
    else:
        print(diagnosis)

    save_run(
        data_date=context["latest_date"],
        current_orders=context["current_orders"],
        historical_average=context["historical_average_7d"],
        volume_ratio=context["volume_ratio"],
        status="BLOCKED",
        diagnosis=diagnosis,
    )


if __name__ == "__main__":
    main()