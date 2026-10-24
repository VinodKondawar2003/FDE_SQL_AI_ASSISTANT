"""Deterministic synthetic data. Never invoked by the query execution surface."""

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path


def seed(path: Path, variant: int = 0) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists; keep it or choose a new path.")
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1042 + variant)
    con = sqlite3.connect(path)
    try:
        con.executescript(Path(__file__).with_name("schema.sql").read_text())
        con.executemany(
            "INSERT INTO departments VALUES (?,?)",
            enumerate(["Sales", "Engineering", "Operations", "Finance"], 1),
        )
        names = ["Avery", "Jordan", "Morgan", "Taylor", "Riley", "Casey", "Alex", "Sam"]
        last = ["Shah", "Chen", "Williams", "Patel", "Garcia", "Kim", "Brown", "Singh"]
        boundaries = ["2023-12-31", "2024-01-01", "2024-01-31", "2024-02-01"]
        for i in range(1, 17):
            hired = boundaries[i - 1] if i <= 4 else (date(2023, 1, 1) + timedelta(days=i * 53)).isoformat()
            con.execute(
                "INSERT INTO employees VALUES (?,?,?,?,?,?,?,?)",
                (
                    i,
                    names[(i - 1) % 8],
                    last[(i - 1) % 8],
                    f"employee{i}@example.test",
                    hired,
                    (i - 1) % 4 + 1,
                    None if i <= 4 else (i - 1) % 4 + 1,
                    6000000 + i * 175000,
                ),
            )
        locations = [("San Francisco", "CA"), ("New York", "NY"), ("Austin", "TX"), ("Los Angeles", "CA")]
        for i in range(1, 81):
            city, state = locations[(i - 1) % 4]
            con.execute(
                "INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
                (
                    i,
                    names[(i - 1) % 8],
                    last[(i - 1) % 8],
                    f"customer{i}@example.test",
                    city,
                    state,
                    f"2023-{(i - 1) % 12 + 1:02d}-01T00:00:00Z",
                ),
            )
        for i in range(1, 31):
            con.execute(
                "INSERT INTO products VALUES (?,?,?,?,?)",
                (
                    i,
                    f"{['Studio', 'Field', 'Everyday'][i % 3]} {['Notebook', 'Desk', 'Lamp', 'Bag', 'Chair'][i % 5]} {i}",
                    ["Office", "Furniture", "Accessories"][i % 3],
                    500 + i * 275,
                    int(i % 7 != 0),
                ),
            )
        item_id = 1
        for i in range(1, 201):
            # Customers 71..80 have no orders; historical prices differ from current prices.
            con.execute(
                "INSERT INTO orders VALUES (?,?,?,?,?)",
                (
                    i,
                    rng.randint(1, 70),
                    None if i % 11 == 0 else rng.randint(1, 16),
                    (date(2024, 1, 1) + timedelta(days=(i * 5) % 1000)).isoformat(),
                    ["paid", "shipped", "pending", "cancelled"][i % 4],
                ),
            )
            for product in rng.sample(range(1, 31), 2 + i % 3):
                con.execute(
                    "INSERT INTO order_items VALUES (?,?,?,?,?)",
                    (item_id, i, product, rng.randint(1, 5), 450 + product * 250 + variant * 10),
                )
                item_id += 1
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=Path("data/sample.db"))
    parser.add_argument("--variant", type=int, default=0)
    args = parser.parse_args()
    seed(args.path, args.variant)
    print(f"Seeded synthetic database: {args.path}")
