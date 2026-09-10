import os

import psycopg
from dotenv import load_dotenv


load_dotenv()

THRESHOLD = 0.70


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_volume_metrics(connection):
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


def check_volume():
    with get_connection() as connection:
        result = get_volume_metrics(connection)

    if result is None:
        raise RuntimeError("Not enough data to perform volume check.")

    order_date, current_volume, historical_average = result
    historical_average = float(historical_average)

    ratio = current_volume / historical_average

    print(f"Date: {order_date}")
    print(f"Current volume: {current_volume}")
    print(f"7-day average: {historical_average:.2f}")
    print(f"Volume ratio: {ratio:.2%}")

    if ratio < THRESHOLD:
        raise RuntimeError(
            f"Volume anomaly detected: {current_volume} orders "
            f"vs {historical_average:.2f} historical average."
        )

    print("Volume check passed.")


if __name__ == "__main__":
    check_volume()