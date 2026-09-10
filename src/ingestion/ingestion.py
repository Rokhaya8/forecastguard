import csv
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


load_dotenv()

DATA_PATH = Path("data/orders.csv")


def get_connection():
    """Create a connection to the ForecastGuard PostgreSQL database."""
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def create_raw_orders_table(connection):
    """Create the raw_orders table if it does not already exist."""
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_orders (
                order_id VARCHAR(20) PRIMARY KEY,
                customer_id VARCHAR(20) NOT NULL,
                product_id VARCHAR(20) NOT NULL,
                order_date DATE NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price NUMERIC(10, 2) NOT NULL
            );
        """)

    connection.commit()


def load_orders(connection):
    """Load orders.csv into the raw_orders table."""

    with DATA_PATH.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        rows = [
            (
                row["order_id"],
                row["customer_id"],
                row["product_id"],
                row["order_date"],
                int(row["quantity"]),
                float(row["unit_price"]),
            )
            for row in reader
        ]

    with connection.cursor() as cursor:

        # V1 strategy: full refresh
        cursor.execute("TRUNCATE TABLE raw_orders;")

        cursor.executemany(
            """
            INSERT INTO raw_orders (
                order_id,
                customer_id,
                product_id,
                order_date,
                quantity,
                unit_price
            )
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            rows,
        )

    connection.commit()

    return len(rows)


def main():
    print("Connecting to PostgreSQL...")

    with get_connection() as connection:
        create_raw_orders_table(connection)
        rows_loaded = load_orders(connection)

    print(f"Successfully loaded {rows_loaded} rows into raw_orders.")


if __name__ == "__main__":
    main()