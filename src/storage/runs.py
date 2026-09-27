import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


CREATE_TABLE_QUERY = """
    CREATE TABLE IF NOT EXISTS forecast_runs (
        id SERIAL PRIMARY KEY,
        executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        data_date DATE NOT NULL,
        current_orders INTEGER NOT NULL,
        historical_average_7d NUMERIC(10, 2) NOT NULL,
        volume_ratio NUMERIC(6, 4) NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('PUBLISHED', 'BLOCKED')),
        forecast_date DATE,
        predicted_orders INTEGER,
        diagnosis TEXT
    );
"""


def create_table(connection):
    with connection.cursor() as cursor:
        cursor.execute(CREATE_TABLE_QUERY)


def save_run(
    data_date,
    current_orders,
    historical_average,
    volume_ratio,
    status,
    forecast_date=None,
    predicted_orders=None,
    diagnosis=None,
):
    insert_query = """
        INSERT INTO forecast_runs (
            data_date,
            current_orders,
            historical_average_7d,
            volume_ratio,
            status,
            forecast_date,
            predicted_orders,
            diagnosis
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """

    with get_connection() as connection:
        create_table(connection)

        with connection.cursor() as cursor:
            cursor.execute(
                insert_query,
                (
                    data_date,
                    current_orders,
                    historical_average,
                    volume_ratio,
                    status,
                    forecast_date,
                    predicted_orders,
                    diagnosis,
                ),
            )

    print(f"Run saved in forecast_runs with status {status}.")


if __name__ == "__main__":
    with get_connection() as connection:
        create_table(connection)

    print("Table forecast_runs is ready.")