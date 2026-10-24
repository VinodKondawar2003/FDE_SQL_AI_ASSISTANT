import sqlite3
import threading
import pytest
from backend.app.errors import AppError


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM customers",
        "UPDATE customers SET state='TX'",
        "INSERT INTO customers VALUES (1)",
        "DROP TABLE customers",
        "ALTER TABLE customers ADD x TEXT",
        "TRUNCATE TABLE customers",
        "SELECT * FROM customers; DROP TABLE customers",
        "PRAGMA table_info(customers)",
        "ATTACH DATABASE 'file.db' AS other",
        "SELECT load_extension('evil')",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM other.customers",
        "WITH RECURSIVE t AS (SELECT 1 UNION ALL SELECT 1 FROM t) SELECT * FROM t",
        "SELECT readfile('/etc/passwd')",
        "CREATE TABLE bad (x)",
        "SELECT * FROM customers c CROSS JOIN orders o",
        "SELECT * FROM customers c JOIN orders o ON c.customer_id=o.order_id",
        "SELECT * FROM customers c JOIN orders o ON c.customer_id=o.customer_id OR 1=1",
        "SELECT * FROM customers c NATURAL JOIN orders o",
        "SELECT * FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE c.customer_id=o.order_id)",
    ],
)
def test_rejects_unsafe_or_unproven(sql, query):
    before = sql.execute("SELECT COUNT(*) FROM customers")["rows"]
    with pytest.raises(AppError):
        sql.validate(query)
    assert sql.execute("SELECT COUNT(*) FROM customers")["rows"] == before


@pytest.mark.parametrize(
    "query",
    [
        "SELECT first_name FROM customers WHERE state='CA'",
        "SELECT * FROM customers WHERE first_name='drop'",
        "SELECT count(*) AS total FROM customers",
        "SELECT customer_id, count(*) AS n FROM orders GROUP BY customer_id HAVING COUNT(*) > 1",
        "SELECT c.customer_id FROM customers c JOIN orders o ON c.customer_id=o.customer_id",
        "SELECT c.customer_id FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id=c.customer_id)",
        "WITH ca AS (SELECT customer_id FROM customers WHERE state='CA') SELECT * FROM ca",
        "WITH ca AS (SELECT customer_id FROM customers) SELECT ca.customer_id FROM ca JOIN orders o ON o.customer_id=ca.customer_id",
        "SELECT e.first_name,m.first_name FROM employees e LEFT JOIN employees m ON e.manager_id=m.employee_id",
        "SELECT state FROM customers UNION SELECT state FROM customers",
        "SELECT first_name, ROW_NUMBER() OVER (ORDER BY customer_id) AS n FROM customers",
    ],
)
def test_valid_queries(sql, query):
    assert sql.execute(query)["returned_row_count"] >= 0


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM imaginary",
        "SELECT imaginary FROM customers",
        "SELECT customer_id FROM customers c JOIN orders o ON c.customer_id=o.customer_id",
        "SELEC name FROM customers",
    ],
)
def test_unknown_or_invalid(sql, query):
    with pytest.raises(AppError):
        sql.validate(query)


def test_dates_and_semantics(sql):
    result = sql.execute(
        "SELECT employee_id FROM employees WHERE hire_date >= '2024-01-01' ORDER BY employee_id"
    )
    ids = [r[0] for r in result["rows"]]
    assert 1 not in ids and all(i in ids for i in [2, 3, 4])
    result = sql.execute("SELECT customer_id FROM customers WHERE state='CA'")
    assert result["returned_row_count"] == 40


def test_proven_join_removal(sql):
    original = "SELECT o.order_id FROM orders o JOIN customers c ON o.customer_id=c.customer_id"
    optimized, notes = sql.optimize(original)
    assert notes["rewrite_applied"]
    assert "JOIN" not in optimized
    assert sorted(sql.execute(original)["rows"]) == sorted(sql.execute(optimized)["rows"])


@pytest.mark.parametrize(
    "query",
    [
        "SELECT c.customer_id FROM customers c JOIN orders o ON c.customer_id=o.customer_id",
        "SELECT o.order_id FROM orders o JOIN employees e ON o.employee_id=e.employee_id",
        "SELECT o.order_id FROM orders o JOIN customers c ON o.customer_id=c.customer_id WHERE c.state='CA'",
    ],
)
def test_preserves_meaningful_joins(sql, query):
    optimized, notes = sql.optimize(query)
    assert "JOIN" in optimized
    assert not notes["rewrite_applied"]


def test_row_limit_and_plan(sql):
    result = sql.execute("SELECT * FROM order_items")
    assert result["returned_row_count"] == 200 and result["truncated"]
    assert sql.plan("SELECT * FROM customers WHERE state='CA'")["steps"]


def test_authorizer_rejects_direct_bypass(sql):
    with sql.connection() as con:
        for query in [
            "DELETE FROM customers",
            "PRAGMA query_only=OFF",
            "SELECT * FROM sqlite_master",
            "ATTACH DATABASE ':memory:' AS x",
            "SELECT randomblob(1000000)",
        ]:
            with pytest.raises(sqlite3.Error):
                con.execute(query)


def test_existing_index_not_recommended(sql):
    assert sql.index_advice("SELECT * FROM customers WHERE state='CA'") == []


def test_cancelled_execution(sql):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(AppError):
        sql.execute("SELECT SUM(quantity) FROM order_items", cancel)


@pytest.mark.parametrize("literal", ["New York", "ca", "California"])
def test_state_filter_rejects_wrong_storage_format(sql, literal):
    with pytest.raises(AppError) as exc:
        sql.validate(f"SELECT customer_id FROM customers WHERE state='{literal}'")
    assert exc.value.code == "INVALID_VALUE"


def test_state_filter_accepts_codes(sql):
    assert (
        sql.execute("SELECT customer_id FROM customers WHERE state IN ('NY', 'CA')")["returned_row_count"]
        > 40
    )
