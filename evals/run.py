"""Real-provider semantic evaluation. Does not mock generation or compare SQL strings."""

import argparse
import asyncio
import json
import tempfile
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.app.agent.graph import Agent
from backend.app.agent.model import GeminiModel
from backend.app.config import Settings
from backend.app.sql.catalog import Catalog
from backend.app.sql.service import SqlService
from backend.app.storage import Store
from data.seed import seed


def equivalent(actual, expected, ordered):
    def normalize(rows):
        return [tuple(round(v, 5) if isinstance(v, float) else v for v in row) for row in rows]

    a, b = normalize(actual), normalize(expected)
    return a == b if ordered else Counter(a) == Counter(b)


class PacedModel(GeminiModel):
    """Space live evaluation calls to respect the provider's free-tier request quota."""

    def __init__(self, settings, store):
        super().__init__(settings, store)
        self.lock = asyncio.Lock()
        self.next_call = 0.0

    async def ask(self, prompt, schema, data):
        async with self.lock:
            await asyncio.sleep(max(0.0, self.next_call - time.monotonic()))
            self.next_call = time.monotonic() + 5.0
        return await super().ask(prompt, schema, data)


async def evaluate(cases, runs, output):
    reports = []
    for run in range(1, runs + 1):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Vary seed distribution across runs to detect accidental equivalence.
            sample = root / "sample.db"
            seed(sample, variant=run - 1)
            settings = Settings(state_dir=root, sample_db=sample)
            if not settings.model_ready:
                raise RuntimeError("Configure GOOGLE_API_KEY and MODEL_NAME before live evaluation.")
            store = Store(root / "app.db")
            sql = SqlService(Catalog(sample))
            model = PacedModel(settings, store)
            async with AsyncSqliteSaver.from_conn_string(str(root / "checkpoints.db")) as saver:
                agent = Agent(model, sql, saver)
                gate = asyncio.Semaphore(2)
                completed = []

                async def evaluate_case(case):
                    async with gate:
                        started = time.monotonic()
                        cid = str(uuid4())
                        history = []
                        record = {"id": case["id"], "category": case["category"], "passed": True, "turns": []}
                        final = None
                        for turn in case["turns"]:
                            try:
                                final = await asyncio.wait_for(
                                    agent.run(
                                        cid, str(uuid4()), str(uuid4()), turn["message"], "auto", history
                                    ),
                                    timeout=settings.turn_timeout,
                                )
                                expected = turn["expected_status"]
                                ok = final["status"] == expected
                                record["passed"] &= ok
                                record["turns"].append(
                                    {
                                        "status": final["status"],
                                        "expected": expected,
                                        "correct_status": ok,
                                        "sql": (final.get("sql") or {}).get("text"),
                                        "explanation": final.get("explanation"),
                                        "clarification": final.get("clarification"),
                                    }
                                )
                                history.append({"user": turn["message"], "assistant": final["message"]})
                                if final.get("sql"):
                                    sql.validate(final["sql"]["text"])
                            except Exception as exc:
                                record["passed"] = False
                                record["turns"].append(
                                    {"error": type(exc).__name__, "code": getattr(exc, "code", None)}
                                )
                                break
                        if record["passed"] and case.get("oracle_sql"):
                            if not final or not final.get("sql"):
                                record["passed"] = False
                            else:
                                actual = sql.execute(final["sql"]["text"])["rows"]
                                expected = sql.execute(case["oracle_sql"])["rows"]
                                record["semantic_match"] = equivalent(actual, expected, case["ordered"])
                                record["passed"] &= record["semantic_match"]
                        record["duration_ms"] = round((time.monotonic() - started) * 1000)
                        print(f"run={run} {case['id']} {'PASS' if record['passed'] else 'FAIL'}", flush=True)
                        completed.append(record)
                        output.parent.mkdir(parents=True, exist_ok=True)
                        output.write_text(
                            json.dumps(
                                reports
                                + [
                                    {
                                        "run": run,
                                        "model": settings.model_name,
                                        "in_progress": True,
                                        "results": completed,
                                    }
                                ],
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                        return record

                results = await asyncio.gather(*(evaluate_case(c) for c in cases))
                counts = {
                    category: {
                        "passed": sum(r["passed"] for r in results if r["category"] == category),
                        "total": sum(r["category"] == category for r in results),
                    }
                    for category in {c["category"] for c in cases}
                }
                reports.append(
                    {
                        "run": run,
                        "model": settings.model_name,
                        "dataset_variant": run - 1,
                        "counts": counts,
                        "results": results,
                    }
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", default="")
    parser.add_argument("--output", type=Path, default=Path("evals/reports/live.json"))
    args = parser.parse_args()
    cases = json.loads(Path("evals/cases.json").read_text())
    if args.only:
        selected = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in selected]
    reports = asyncio.run(evaluate(cases, args.runs, args.output))
    print(json.dumps([{"run": r["run"], "counts": r["counts"]} for r in reports], indent=2))
    # Use strict all-pass exit for automation; the documented minimum release thresholds are reviewed separately.
    raise SystemExit(0 if all(x["passed"] for r in reports for x in r["results"]) else 1)
