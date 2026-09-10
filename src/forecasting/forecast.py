import os
from datetime import timedelta

import psycopg
from dotenv import load_dotenv

from src.quality.volume_check import check_volume


load_dotenv()

FORECAST_WINDOW = 7


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_recent_sales(connection):
    query = """
        SELECT
            order_date,
            number_of_orders
        FROM analytics.fct_daily_sales
        ORDER BY order_date DESC
        LIMIT %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (FORECAST_WINDOW,))
        rows = cursor.fetchall()

    return rows


def generate_forecast():
    print("Running data quality check...")

    # If this raises an exception, forecasting stops here.
    check_volume()

    print("Data quality check passed.")
    print("Generating forecast...")

    with get_connection() as connection:
        rows = get_recent_sales(connection)

    if len(rows) < FORECAST_WINDOW:
        raise RuntimeError(
            f"Not enough historical data. "
            f"Expected {FORECAST_WINDOW} days, found {len(rows)}."
        )

    latest_date = rows[0][0]

    volumes = [
        row[1]
        for row in rows
    ]

    predicted_orders = sum(volumes) / len(volumes)
    forecast_date = latest_date + timedelta(days=1)

    print(f"Forecast date: {forecast_date}")
    print(f"Forecast window: {FORECAST_WINDOW} days")
    print(f"Predicted orders: {predicted_orders:.0f}")

    return {
        "forecast_date": forecast_date,
        "predicted_orders": predicted_orders,
    }


if __name__ == "__main__":
    generate_forecast()