import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

TABLE_COLUMNS = {
    "departments": "department_id name",
    "employees": "employee_id first_name last_name email hire_date department_id manager_id salary_cents",
    "customers": "customer_id first_name last_name email city state created_at",
    "products": "product_id name category unit_price_cents active",
    "orders": "order_id customer_id employee_id order_date status",
    "order_items": "order_item_id order_id product_id quantity unit_price_cents",
}


class Catalog:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.tables = {}
        self.relationships = []
        self.indexes = {}
        self.schema = {}
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as con:
            if con.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Sample database foreign keys are invalid.")
            for name, expected in TABLE_COLUMNS.items():
                cols = con.execute(f'PRAGMA table_info("{name}")').fetchall()
                if [c[1] for c in cols] != expected.split():
                    raise ValueError(f"Unexpected schema for {name}. Rebuild the sample database.")
                self.tables[name] = [
                    {"name": c[1], "type": c[2], "nullable": not (c[3] or c[5]), "primary_key": bool(c[5])}
                    for c in cols
                ]
                self.schema[name] = {c[1]: c[2] for c in cols}
                self.indexes[name] = []
                for idx in con.execute(f'PRAGMA index_list("{name}")'):
                    self.indexes[name].append([c[2] for c in con.execute(f'PRAGMA index_info("{idx[1]}")')])
                for fk in con.execute(f'PRAGMA foreign_key_list("{name}")'):
                    self.relationships.append(
                        {"from_table": name, "from_column": fk[3], "to_table": fk[2], "to_column": fk[4]}
                    )
        self.dictionary = json.loads(Path("data/dictionary.json").read_text())
        self.version = (
            "demo-v1-"
            + hashlib.sha256(
                json.dumps([self.tables, self.relationships], sort_keys=True).encode()
            ).hexdigest()[:12]
        )

    def as_dict(self):
        return {
            "version": self.version,
            "dialect": "sqlite",
            "tables": self.tables,
            "relationships": self.relationships,
            "indexes": self.indexes,
            "dictionary": self.dictionary,
        }

    def is_relationship(self, left, right):
        return any(
            {left, right} == {(r["from_table"], r["from_column"]), (r["to_table"], r["to_column"])}
            for r in self.relationships
        )

    def not_null(self, table, column):
        return next((not c["nullable"] for c in self.tables[table] if c["name"] == column), False)
