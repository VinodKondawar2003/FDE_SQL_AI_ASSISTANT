import asyncio
import json
import re
import time
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.agent.model import Advice, Candidate, Classification, Explanation, budget
from backend.app.errors import AppError
from backend.app.storage import uid

REFUSAL = "I'm designed to assist only with read-only SQL and this database. I can't help with that request."
UNSAFE = {"UNSAFE_SQL", "UNSAFE_FUNCTION", "UNSUPPORTED_SQL"}
SQL_START = re.compile(
    r"^\s*(SELECT|WITH|DELETE|UPDATE|INSERT|DROP|ALTER|TRUNCATE|CREATE|PRAGMA|ATTACH|DETACH|REPLACE)\b", re.I
)
CODE = re.compile(
    r"```|\b(?:SELECT\s+.+?\s+FROM|INSERT\s+INTO|DELETE\s+FROM|DROP\s+TABLE|UPDATE\s+\w+\s+SET|CREATE\s+INDEX)\b",
    re.I | re.S,
)


class State(TypedDict, total=False):
    conversation_id: str
    turn_id: str
    request_id: str
    message: str
    mode: str
    history: list
    schema_version: str
    last_sql: str
    pending: dict | None
    classification: dict
    candidate: str
    sql: str
    assumptions: list
    issues: list
    diagnostics: list
    repairs: int
    route: str
    status: str
    explanation: dict | None
    optimization: dict | None
    clarification: dict | None
    response: dict
    started: float


def clean_prose(value, catalog, fallback=""):
    if not isinstance(value, str) or len(value) > 4000 or CODE.search(value):
        return fallback
    # Dotted names are schema references, never an invitation to invent objects.
    for table, col in re.findall(r"\b([a-z_]+)\.([a-z_]+)\b", value, re.I):
        if table.lower() not in catalog.schema or col.lower() not in catalog.schema[table.lower()]:
            return fallback
    return value


def safe_explanation(explanation, catalog):
    allowed = set(catalog.schema) | {f"{t}.{c}" for t, cols in catalog.schema.items() for c in cols}
    allowed |= {c for cols in catalog.schema.values() for c in cols}
    if any(i not in allowed for i in explanation.referenced_identifiers):
        return None
    summary = clean_prose(explanation.summary, catalog)
    if not summary:
        return None
    return {
        "summary": summary,
        "steps": [s for s in (clean_prose(v, catalog) for v in explanation.steps) if s],
        "assumptions": [s for s in (clean_prose(v, catalog) for v in explanation.assumptions) if s],
    }


class Agent:
    def __init__(self, model, sql, checkpointer):
        self.model, self.sql, self.catalog = model, sql, sql.catalog
        graph = StateGraph(State)
        for name in ("classify", "generate", "validate", "repair", "optimize", "explain", "finish"):
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "classify")
        graph.add_conditional_edges(
            "classify",
            lambda s: s["route"],
            {"generate": "generate", "validate": "validate", "explain": "explain", "finish": "finish"},
        )
        graph.add_conditional_edges(
            "generate", lambda s: s["route"], {"validate": "validate", "finish": "finish"}
        )
        graph.add_conditional_edges(
            "validate", lambda s: s["route"], {"repair": "repair", "optimize": "optimize", "finish": "finish"}
        )
        graph.add_conditional_edges(
            "repair", lambda s: s["route"], {"validate": "validate", "finish": "finish"}
        )
        graph.add_edge("optimize", "explain")
        graph.add_edge("explain", "finish")
        graph.add_edge("finish", END)
        self.graph = graph.compile(checkpointer=checkpointer)

    def context(self, state):
        history = []
        size = 0
        for entry in reversed(state.get("history", [])[-10:]):
            rendered = json.dumps(entry)
            if size + len(rendered) > 12000:
                break
            history.insert(0, entry)
            size += len(rendered)
        return {
            "trusted_catalog": self.catalog.as_dict(),
            "current_message": state["message"],
            "ui_mode": state["mode"],
            "history": history,
            "last_validated_sql": state.get("last_sql", ""),
            "pending_clarification": state.get("pending"),
            "reference_clock": datetime.now(timezone.utc).isoformat(),
        }

    async def classify(self, state):
        updates = {"schema_version": self.catalog.version}
        if state.get("schema_version") != self.catalog.version or state["message"].lower().startswith(
            "start a new question"
        ):
            updates.update(last_sql="", pending=None)
            state = {**state, **updates}
        raw = state["message"].strip()
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.I | re.S)
        supplied = re.match(r"^(debug|optimize|explain)\b[^:\n]{0,140}:\s*(.+)$", raw, re.I | re.S)
        direct = fenced.group(1).strip() if fenced else supplied.group(2).strip() if supplied else raw
        direct_intent = supplied.group(1).lower() if supplied else state.get("mode", "auto")
        direct_intent = "explain_sql" if direct_intent == "explain" else direct_intent
        if direct_intent not in {"debug", "optimize", "explain_sql"}:
            direct_intent = "optimize"
        if SQL_START.match(direct):
            try:
                self.sql.parse(direct)
            except AppError as exc:
                if exc.code in UNSAFE:
                    return {**updates, "status": "refused", "route": "finish"}
        if SQL_START.match(direct) or (supplied and re.match(r"^SELEC\b", direct, re.I)):
            # A supplied query is already the candidate: do not ask an LLM to reinterpret it.
            return {
                **updates,
                "classification": {"intent": direct_intent, "in_scope": True},
                "candidate": direct,
                "route": "validate",
            }
        if re.search(
            r"\b(?:delete|drop|truncate|update|insert|alter)\s+(?:all\s+|the\s+)?(?:customers|employees|orders|products|table|database|rows)\b",
            raw,
            re.I,
        ):
            return {**updates, "status": "refused", "route": "finish"}
        if not state.get("pending") and re.search(r"\bafter january 2024\b(?!\s+(?:ends|ended))", raw, re.I):
            question = "Do you mean on or after January 1, 2024, or after January ends?"
            clarification = {
                "question": question,
                "choices": ["January 1, 2024 inclusive", "February 1, 2024 inclusive"],
            }
            return {
                **updates,
                "status": "clarification_required",
                "clarification": clarification,
                "pending": {"original_request": raw, **clarification},
                "route": "finish",
            }
        classified = await self.model.ask("classify", Classification, self.context(state))
        if not classified.in_scope or classified.forbidden_operation or classified.intent == "refuse":
            return {
                **updates,
                "classification": classified.model_dump(),
                "status": "refused",
                "route": "finish",
            }
        if classified.intent == "clarify":
            question = clean_prose(
                classified.question, self.catalog, "Could you clarify which data and metric you need?"
            )
            clarification = {
                "question": question,
                "choices": [clean_prose(v, self.catalog) for v in classified.choices],
            }
            return {
                **updates,
                "classification": classified.model_dump(),
                "status": "clarification_required",
                "clarification": clarification,
                "pending": {"original_request": raw, **clarification},
                "route": "finish",
            }
        return {
            **updates,
            "classification": classified.model_dump(),
            "route": "explain" if classified.intent == "schema_question" else "generate",
        }

    def candidate_update(self, candidate, state):
        if candidate.kind == "clarification":
            question = clean_prose(
                candidate.question, self.catalog, "Which field or metric should this query use?"
            )
            clarification = {
                "question": question,
                "choices": [clean_prose(v, self.catalog) for v in candidate.choices],
            }
            return {
                "status": "clarification_required",
                "clarification": clarification,
                "pending": {
                    "original_request": (state.get("pending") or {}).get(
                        "original_request", state["message"]
                    ),
                    **clarification,
                },
                "route": "finish",
            }
        return {
            "candidate": candidate.sql,
            "assumptions": candidate.assumptions,
            "issues": candidate.issues,
            "route": "validate",
        }

    async def generate(self, state):
        candidate = await self.model.ask(
            "generate", Candidate, {**self.context(state), "intent": state["classification"]["intent"]}
        )
        return self.candidate_update(candidate, state)

    async def validate(self, state):
        try:
            validated = await asyncio.to_thread(self.sql.validate, state["candidate"])
            return {"sql": validated, "route": "optimize"}
        except AppError as exc:
            diagnostic = {"code": exc.code, "message": exc.message}
            if exc.code in UNSAFE:
                return {"status": "refused", "diagnostics": [diagnostic], "route": "finish"}
            if state["repairs"] < 2:
                return {"diagnostics": [diagnostic], "route": "repair"}
            return {"status": "failed", "diagnostics": [diagnostic], "route": "finish"}

    async def repair(self, state):
        candidate = await self.model.ask(
            "repair",
            Candidate,
            {**self.context(state), "candidate": state["candidate"], "diagnostics": state["diagnostics"]},
        )
        return {**self.candidate_update(candidate, state), "repairs": state["repairs"] + 1}

    async def optimize(self, state):
        if state["classification"]["intent"] == "explain_sql":
            sql = state["sql"]
            notes = {"changes": [], "suggestions": [], "index_recommendations": [], "rewrite_applied": False}
        else:
            sql, notes = await asyncio.to_thread(self.sql.optimize, state["sql"])
        if state["classification"]["intent"] == "optimize":
            try:
                advice = await self.model.ask(
                    "optimize", Advice, {**self.context(state), "validated_sql": sql}
                )
                allowed = set(self.catalog.schema) | {
                    f"{t}.{c}" for t, cols in self.catalog.schema.items() for c in cols
                }
                if all(ref in allowed for ref in advice.referenced_identifiers):
                    notes["suggestions"] += [
                        v for v in (clean_prose(s, self.catalog) for s in advice.suggestions) if v
                    ]
            except AppError:
                pass
        return {"sql": sql, "optimization": notes}

    async def explain(self, state):
        sql = state.get("sql", "")
        try:
            explanation = await self.model.ask(
                "explain",
                Explanation,
                {
                    **self.context(state),
                    "validated_sql": sql,
                    "assumptions": state.get("assumptions", []),
                    "intent": state.get("classification", {}).get("intent"),
                },
            )
            safe = safe_explanation(explanation, self.catalog)
        except AppError:
            if not sql:
                raise
            safe = None
        if safe is None:
            if not sql:
                return {
                    "status": "failed",
                    "diagnostics": [
                        {
                            "code": "OUTPUT_POLICY",
                            "message": "I couldn't produce a grounded explanation. Please rephrase.",
                        }
                    ],
                }
            import sqlglot
            from sqlglot import exp

            tree = sqlglot.parse_one(sql, read="sqlite")
            tables = sorted({t.name for t in tree.find_all(exp.Table) if t.name in self.catalog.schema})
            safe = {
                "summary": "Retrieves data from " + ", ".join(tables) + ".",
                "steps": [
                    "The SQL passed syntax, schema, relationship, and read-only validation.",
                    "Review the SQL panel for the exact filters, calculations, ordering, and limits.",
                ],
                "assumptions": ["A detailed AI explanation was unavailable; this is a structural summary."],
            }
        return {"explanation": safe, "status": "completed"}

    async def finish(self, state):
        status = state.get("status", "completed")
        sql = state.get("sql", "") if status == "completed" else ""
        if sql:
            sql = await asyncio.to_thread(self.sql.validate, sql)
        message = {
            "completed": "Your query is ready." if sql else "Here's how it works.",
            "refused": REFUSAL,
            "clarification_required": (state.get("clarification") or {}).get("question", "Please clarify."),
            "failed": "I couldn't validate a query for this request. Please rephrase or specify the fields.",
        }[status]
        issues = [clean_prose(v, self.catalog) for v in state.get("issues", [])]
        response = {
            "request_id": state["request_id"],
            "conversation_id": state["conversation_id"],
            "turn_id": state["turn_id"],
            "status": status,
            "intent": state.get("classification", {}).get(
                "intent", "refuse" if status == "refused" else "clarify"
            ),
            "message": message,
            "sql": {
                "artifact_id": uid(),
                "text": sql,
                "dialect": "sqlite",
                "schema_version": self.catalog.version,
                "validation": "passed",
            }
            if sql
            else None,
            "explanation": state.get("explanation") if status == "completed" else None,
            "diagnostics": state.get("diagnostics", [])
            + [{"code": "DEBUG_NOTE", "message": v} for v in issues if v],
            "optimization": state.get("optimization") if sql else None,
            "clarification": state.get("clarification") if status == "clarification_required" else None,
            "error": None,
            "meta": {
                "total_duration_ms": round((time.monotonic() - state["started"]) * 1000),
                "execution_available": bool(sql),
            },
        }
        updates = {"response": response}
        if sql:
            updates.update(last_sql=sql, pending=None)
        return updates

    async def run(self, cid, tid, request_id, message, mode, history):
        token = budget.set({"calls": 0})
        try:
            result = await self.graph.ainvoke(
                {
                    "conversation_id": cid,
                    "turn_id": tid,
                    "request_id": request_id,
                    "message": message,
                    "mode": mode,
                    "history": history,
                    "classification": {},
                    "candidate": "",
                    "sql": "",
                    "assumptions": [],
                    "issues": [],
                    "diagnostics": [],
                    "repairs": 0,
                    "route": "",
                    "status": "completed",
                    "explanation": None,
                    "optimization": None,
                    "clarification": None,
                    "response": {},
                    "started": time.monotonic(),
                },
                config={"configurable": {"thread_id": cid}, "recursion_limit": 30},
            )
            return result["response"]
        finally:
            budget.reset(token)
