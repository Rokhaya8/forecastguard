import csv
import random
from datetime import date
from pathlib import Path


DATA_PATH = Path("data/orders.csv")

ANOMALY_DATE = date(2026, 8, 15)
ANOMALY_ORDERS = 150

CUSTOMERS = 800
PRODUCTS = 40


def generate_customer_id() -> str:
    return f"CUST{random.randint(1, CUSTOMERS):04d}"


def generate_product_id() -> str:
    return f"PROD{random.randint(1, PRODUCTS):03d}"


def generate_quantity() -> int:
    return random.randint(1, 4)


def generate_unit_price() -> float:
    return round(random.uniform(8.0, 120.0), 2)


def get_next_order_number(rows):
    max_number = 0

    for row in rows:
        number = int(row["order_id"].replace("ORD", ""))
        max_number = max(max_number, number)

    return max_number + 1


def main():
    random.seed(123)

    with DATA_PATH.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    anomaly_date_str = ANOMALY_DATE.isoformat()

    # Avoid adding the anomaly twice
    existing_rows = [
        row for row in rows
        if row["order_date"] == anomaly_date_str
    ]

    if existing_rows:
        print(
            f"Anomaly date {anomaly_date_str} already exists "
            f"with {len(existing_rows)} orders."
        )
        return

    next_order_number = get_next_order_number(rows)

    new_rows = []

    for offset in range(ANOMALY_ORDERS):
        new_rows.append({
            "order_id": f"ORD{next_order_number + offset:06d}",
            "customer_id": generate_customer_id(),
            "product_id": generate_product_id(),
            "order_date": anomaly_date_str,
            "quantity": generate_quantity(),
            "unit_price": generate_unit_price(),
        })

    rows.extend(new_rows)

    fieldnames = [
        "order_id",
        "customer_id",
        "product_id",
        "order_date",
        "quantity",
        "unit_price",
    ]

    with DATA_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Added {ANOMALY_ORDERS} anomalous orders "
        f"for {anomaly_date_str}."
    )


if __name__ == "__main__":
    main()