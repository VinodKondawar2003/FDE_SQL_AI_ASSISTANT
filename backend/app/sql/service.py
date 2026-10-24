"""An allowlisted SQL boundary independent of the language model."""

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope

from backend.app.errors import AppError

VALIDATOR_VERSION = "1"
FUNCTIONS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "coalesce",
    "ifnull",
    "nullif",
    "round",
    "abs",
    "lower",
    "upper",
    "length",
    "trim",
    "substr",
    "substring",
    "date",
    "datetime",
    "strftime",
    "julianday",
    "row_number",
    "rank",
    "dense_rank",
    "lag",
    "lead",
    "like",
}
# No generic expression fallback: newly introduced parser constructs fail closed.
NODES = set(
    """
select from table tablealias identifier column literal star alias where and or not
eq neq gt gte lt lte is null boolean between in exists paren neg add sub mul div mod
order ordered group having limit offset distinct join with cte subquery union intersect
except window windowspec partition tuple cast datatype datatypeparam case if filter
escape collate
""".split()
)
FUNCTION_KEYS = set(
    """
count sum avg min max coalesce nullif round abs lower upper length trim substring
date datetime strftotime timetostr tsordstodate tsordstotime julianday rownumber rank
denserank lag lead anonymous like
""".split()
)


def digest(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()


class SqlService:
    def __init__(self, catalog, timeout=2.0):
        self.catalog, self.timeout = catalog, timeout

    @contextmanager
    def connection(self, cancel=None):
        con = sqlite3.connect(
            self.catalog.path.as_uri() + "?mode=ro", uri=True, timeout=1, check_same_thread=False
        )
        try:
            con.execute("PRAGMA query_only=ON")
            if hasattr(con, "enable_load_extension"):
                con.enable_load_extension(False)
            for limit, value in [
                (sqlite3.SQLITE_LIMIT_SQL_LENGTH, 16000),
                (sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 50),
                (sqlite3.SQLITE_LIMIT_COLUMN, 100),
                (sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 10),
                (sqlite3.SQLITE_LIMIT_LENGTH, 1000000),
            ]:
                con.setlimit(limit, value)

            def authorize(action, arg1, arg2, database, trigger):
                if action == sqlite3.SQLITE_SELECT:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_READ:
                    if (
                        (database == "main" or (database is None and arg2 == ""))
                        and arg1 in self.catalog.schema
                        and (not arg2 or arg2 in self.catalog.schema[arg1])
                    ):
                        return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() in FUNCTIONS:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            con.set_authorizer(authorize)
            deadline = time.monotonic() + self.timeout
            con.set_progress_handler(
                lambda: int(time.monotonic() > deadline or (cancel is not None and cancel.is_set())), 500
            )
            yield con
        finally:
            con.close()

    def parse(self, sql):
        if not sql or len(sql) > 16000:
            raise AppError("SQL_SIZE", "Provide a single query under 16,000 characters.")
        try:
            statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
        except sqlglot.errors.ParseError:
            raise AppError("SQL_SYNTAX", "The SQL syntax is invalid. Check punctuation and clauses.")
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.SetOperation)):
            raise AppError("UNSAFE_SQL", "Only one read-only SELECT query is allowed.")
        tree = statements[0]
        for node in tree.walk():
            if node.key not in NODES | FUNCTION_KEYS:
                raise AppError("UNSUPPORTED_SQL", "This query uses an unsupported SQL operation.")
            if isinstance(node, exp.With) and node.args.get("recursive"):
                raise AppError("UNSAFE_SQL", "Recursive queries are not supported.")
            if isinstance(node, exp.Table) and (node.db or node.catalog):
                raise AppError("UNSAFE_SQL", "External or qualified database access is not allowed.")
            if isinstance(node, exp.Anonymous) and node.name.lower() not in FUNCTIONS:
                raise AppError("UNSAFE_FUNCTION", "This SQL function is not permitted.")
            if isinstance(node, exp.Join) and (
                node.args.get("method") or node.args.get("side") in {"FULL", "RIGHT"}
            ):
                raise AppError(
                    "UNSUPPORTED_JOIN", "Use explicit INNER or LEFT joins on declared relationships."
                )
        return tree

    def validate(self, sql):
        tree = self.parse(sql)
        try:
            tree = qualify(
                tree,
                dialect="sqlite",
                schema=self.catalog.schema,
                allow_partial_qualification=False,
                validate_qualify_columns=True,
            )
        except (sqlglot.errors.OptimizeError, sqlglot.errors.SchemaError):
            raise AppError("SCHEMA_REFERENCE", "A table or column is unknown or ambiguous in this schema.")
        self._relationships(tree)
        canonical = tree.sql(dialect="sqlite", pretty=True)
        self.parse(canonical)
        try:
            with self.connection() as con:
                con.execute("EXPLAIN QUERY PLAN " + canonical).fetchall()
        except sqlite3.Error as exc:
            code = "QUERY_TIMEOUT" if "interrupted" in str(exc) else "ENGINE_VALIDATION"
            raise AppError(code, "The query could not be validated safely against SQLite.")
        return canonical

    def _resolve(self, scope, column, seen=None):
        seen = set() if seen is None else seen
        marker = (id(scope), column.table, column.name)
        if marker in seen:
            return None
        seen.add(marker)
        source = scope.sources.get(column.table)
        if source is None and scope.parent:
            return self._resolve(scope.parent, column, seen)
        if isinstance(source, exp.Table):
            return (source.name, column.name)
        if isinstance(source, Scope):
            expression = source.expression
            if not isinstance(expression, exp.Select):
                return None
            for projection in expression.selects:
                if projection.alias_or_name == column.name:
                    actual = projection.this if isinstance(projection, exp.Alias) else projection
                    if isinstance(actual, exp.Column):
                        return self._resolve(source, actual, seen)
        return None

    @staticmethod
    def _conjuncts(expr):
        if isinstance(expr, exp.Paren):
            return SqlService._conjuncts(expr.this)
        if isinstance(expr, exp.And):
            return SqlService._conjuncts(expr.left) + SqlService._conjuncts(expr.right)
        return [expr] if expr is not None else []

    def _relationships(self, tree):
        for scope in traverse_scope(tree):
            if not isinstance(scope.expression, exp.Select):
                continue
            select = scope.expression
            aliases = list(scope.selected_sources)
            edges = set()
            predicates = [j.args.get("on") for j in select.args.get("joins", [])]
            if select.args.get("where"):
                predicates.append(select.args["where"].this)
            for predicate in predicates:
                for node in self._conjuncts(predicate):
                    if (
                        isinstance(node, exp.EQ)
                        and isinstance(node.left, exp.Column)
                        and isinstance(node.right, exp.Column)
                    ):
                        left, right = node.left, node.right
                        if left.table != right.table:
                            a, b = self._resolve(scope, left), self._resolve(scope, right)
                            if a and b and self.catalog.is_relationship(a, b):
                                edges.add(frozenset((left.table, right.table)))
            # The schema stores state codes, so a full state name would silently return wrong results.
            for predicate in scope.columns:
                if self._resolve(scope, predicate) != ("customers", "state"):
                    continue
                parent = predicate.parent
                literals = []
                if isinstance(parent, exp.EQ):
                    other = parent.right if parent.left is predicate else parent.left
                    literals = [other]
                elif isinstance(parent, exp.In) and parent.this is predicate:
                    literals = parent.expressions
                for literal in literals:
                    if (
                        isinstance(literal, exp.Literal)
                        and literal.is_string
                        and (
                            len(literal.this) != 2 or not literal.this.isupper() or not literal.this.isalpha()
                        )
                    ):
                        raise AppError(
                            "INVALID_VALUE",
                            "customers.state stores two-letter US codes such as CA, NY, and TX.",
                        )
            # Every local relation must be joined to earlier relations on an unconditional FK equality.
            if len(aliases) > 1:
                reached = {aliases[0]}
                while True:
                    expanded = reached | {a for edge in edges if edge & reached for a in edge if a in aliases}
                    if expanded == reached:
                        break
                    reached = expanded
                if reached != set(aliases):
                    raise AppError("INVALID_JOIN", "Join tables using a declared foreign-key relationship.")
            # An arbitrary correlation must not evade the same relationship boundary.
            external = {c.table for c in scope.external_columns if c.table and c.table not in aliases}
            for alias in external:
                if not any(alias in edge and any(a in aliases for a in edge) for edge in edges):
                    raise AppError("INVALID_JOIN", "The correlated query needs a declared relationship.")

    def optimize(self, sql):
        original = self.validate(sql)
        tree = sqlglot.parse_one(original, read="sqlite")
        changes = []
        if isinstance(tree, exp.Select):
            sources = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
            for join in list(tree.args.get("joins", [])):
                if not isinstance(join.this, exp.Table):
                    continue
                alias, parent = join.this.alias_or_name, join.this.name
                on = join.args.get("on")
                if not isinstance(on, exp.EQ) or not all(
                    isinstance(c, exp.Column) for c in (on.left, on.right)
                ):
                    continue
                other_nodes = [
                    c for c in tree.find_all(exp.Column) if c.table == alias and c not in list(on.walk())
                ]
                if other_nodes:
                    continue
                child_col = on.right if on.left.table == alias else on.left
                parent_col = on.left if on.left.table == alias else on.right
                child = sources.get(child_col.table)
                relationship = next(
                    (
                        r
                        for r in self.catalog.relationships
                        if (r["from_table"], r["from_column"], r["to_table"], r["to_column"])
                        == (child, child_col.name, parent, parent_col.name)
                    ),
                    None,
                )
                if not relationship:
                    continue
                pk = any(
                    c["name"] == parent_col.name and c["primary_key"] for c in self.catalog.tables[parent]
                )
                safe_inner = self.catalog.not_null(child, child_col.name)
                if pk and (join.side == "LEFT" or (not join.side and safe_inner)):
                    tree.set("joins", [j for j in tree.args.get("joins", []) if j is not join])
                    changes.append(
                        f"Removed the unused {parent} join; the declared key proves unchanged row multiplicity."
                    )
        try:
            final = self.validate(tree.sql(dialect="sqlite"))
        except AppError:
            final, changes = original, []
        return final, {
            "changes": ["Formatted SQL and qualified column references.", *changes],
            "suggestions": ["Inspect the query plan before assuming an index will improve performance."],
            "index_recommendations": self.index_advice(final),
            "rewrite_applied": bool(changes),
        }

    def index_advice(self, sql):
        tree = sqlglot.parse_one(sql, read="sqlite")
        sources = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
        advice = []
        for clause in [*tree.find_all(exp.Where), *tree.find_all(exp.Order)]:
            for col in clause.find_all(exp.Column):
                table = sources.get(col.table)
                if table not in self.catalog.tables:
                    continue
                if any(c["primary_key"] and c["name"] == col.name for c in self.catalog.tables[table]):
                    continue
                if not any(idx and idx[0] == col.name for idx in self.catalog.indexes[table]):
                    text = f"Consider an index on {table}.{col.name} for this filter or ordering; measure its benefit."
                    if text not in advice:
                        advice.append(text)
        return advice

    def plan(self, sql):
        final = self.validate(sql)
        with self.connection() as con:
            rows = con.execute("EXPLAIN QUERY PLAN " + final).fetchall()
        return {
            "steps": [{"id": r[0], "parent": r[1], "detail": r[3]} for r in rows],
            "observations": ["SQLite shows access paths, not a numeric cost estimate."],
        }

    def execute(self, sql, cancel: threading.Event | None = None):
        start = time.monotonic()
        final = self.validate(sql)
        try:
            with self.connection(cancel) as con:
                cursor = con.execute(final)
                raw = cursor.fetchmany(201)
                rows = raw[:200]
                columns = []
                for i, description in enumerate(cursor.description):
                    value = next((r[i] for r in rows if r[i] is not None), None)
                    kind = (
                        "integer"
                        if isinstance(value, int)
                        else "number"
                        if isinstance(value, float)
                        else "null"
                        if value is None
                        else "text"
                    )
                    columns.append({"name": description[0], "type": kind})
                safe_rows = []
                for row in rows:
                    if any(isinstance(v, bytes) for v in row):
                        raise AppError("RESULT_TYPE", "Binary query results are not supported.")
                    safe_rows.append(
                        [str(v) if isinstance(v, int) and abs(v) > 9007199254740991 else v for v in row]
                    )
                result = {
                    "columns": columns,
                    "rows": safe_rows,
                    "returned_row_count": len(rows),
                    "truncated": len(raw) > 200,
                    "limit": 200,
                    "duration_ms": round((time.monotonic() - start) * 1000),
                }
                if len(json.dumps(result).encode()) > 1000000:
                    raise AppError("RESULT_LIMIT", "The result is too large. Select fewer columns or rows.")
                return result
        except sqlite3.Error as exc:
            if "interrupted" in str(exc):
                raise AppError("QUERY_TIMEOUT", "The query exceeded its execution budget.", 504, True)
            raise AppError("EXECUTION_FAILED", "SQLite could not execute this query safely.")
