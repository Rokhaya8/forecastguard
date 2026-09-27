import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from src.quality.volume_check import evaluate_volume
from src.storage.runs import save_run


load_dotenv()

MODEL_NAME = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 20


def build_prompt(metrics):
    return f"""
You are a data reliability assistant.

Analyze only the evidence provided below.

Pipeline context:
- Pipeline: ForecastGuard
- dbt transformations: completed successfully
- dbt structural tests (not_null, unique on order_id): passed
- Volume quality check: anomaly detected
- Forecast status: BLOCKED
- Latest date: {metrics["data_date"]}
- Current orders: {metrics["current_orders"]}
- 7-day historical average: {metrics["historical_average"]}
- Volume ratio: {metrics["volume_ratio"]:.2%}

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


def get_llm_diagnosis(metrics):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the environment.")

    client = genai.Client(api_key=api_key)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=build_prompt(metrics),
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
    metrics = evaluate_volume()

    if metrics["passed"]:
        print("No volume anomaly detected: nothing to diagnose.")
        return

    print("\nLLM diagnosis")
    print("-------------")

    diagnosis = get_llm_diagnosis(metrics)

    if diagnosis is None:
        print(
            "Diagnosis unavailable: Gemini did not respond. "
            "The incident details above remain valid."
        )
    else:
        print(diagnosis)

    save_run(
        data_date=metrics["data_date"],
        current_orders=metrics["current_orders"],
        historical_average=metrics["historical_average"],
        volume_ratio=metrics["volume_ratio"],
        status="BLOCKED",
        diagnosis=diagnosis,
    )


if __name__ == "__main__":
    main()