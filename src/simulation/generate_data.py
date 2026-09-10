import csv
import random
from datetime import date, timedelta
from pathlib import Path


OUTPUT_PATH = Path("data/orders.csv")

START_DATE = date(2026, 7, 1)
NUM_DAYS = 45

CUSTOMERS = 800
PRODUCTS = 40

MIN_DAILY_ORDERS = 900
MAX_DAILY_ORDERS = 1100


def generate_order_id(counter: int) -> str:
    return f"ORD{counter:06d}"


def generate_customer_id() -> str:
    return f"CUST{random.randint(1, CUSTOMERS):04d}"


def generate_product_id() -> str:
    return f"PROD{random.randint(1, PRODUCTS):03d}"


def generate_quantity() -> int:
    return random.randint(1, 4)


def generate_unit_price() -> float:
    return round(random.uniform(8.0, 120.0), 2)


def generate_orders():
    random.seed(42)

    orders = []
    order_counter = 1

    for day_offset in range(NUM_DAYS):
        current_date = START_DATE + timedelta(days=day_offset)

        daily_orders = random.randint(
            MIN_DAILY_ORDERS,
            MAX_DAILY_ORDERS
        )

        for _ in range(daily_orders):
            orders.append(
                {
                    "order_id": generate_order_id(order_counter),
                    "customer_id": generate_customer_id(),
                    "product_id": generate_product_id(),
                    "order_date": current_date.isoformat(),
                    "quantity": generate_quantity(),
                    "unit_price": generate_unit_price(),
                }
            )

            order_counter += 1

    return orders


def save_orders(orders):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "order_id",
        "customer_id",
        "product_id",
        "order_date",
        "quantity",
        "unit_price",
    ]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(orders)


def main():
    orders = generate_orders()
    save_orders(orders)

    print(f"{len(orders)} orders generated.")
    print(f"Dataset saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()