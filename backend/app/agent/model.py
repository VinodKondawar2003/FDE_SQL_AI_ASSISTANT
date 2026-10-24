import asyncio
import contextvars
import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.errors import AppError

budget = contextvars.ContextVar("model_budget", default=None)
log = logging.getLogger("querycraft.model")


class Classification(BaseModel):
    intent: Literal[
        "generate", "follow_up", "optimize", "debug", "explain_sql", "schema_question", "clarify", "refuse"
    ]
    in_scope: bool
    forbidden_operation: bool = False
    question: str = ""
    choices: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    kind: Literal["sql", "clarification"]
    sql: str = ""
    question: str = ""
    choices: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class Explanation(BaseModel):
    summary: str
    steps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    referenced_identifiers: list[str] = Field(default_factory=list)


class Advice(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
    referenced_identifiers: list[str] = Field(default_factory=list)


class GeminiModel:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.client = None
        if settings.model_ready:
            from langchain_google_genai import ChatGoogleGenerativeAI

            self.client = ChatGoogleGenerativeAI(
                model=settings.model_name,
                api_key=settings.google_api_key,
                max_output_tokens=2000,
                max_retries=0,
                timeout=15,
            )
        prompt_dir = Path(__file__).parents[1] / "prompts"
        self.prompts = {p.stem: p.read_text(encoding="utf-8") for p in prompt_dir.glob("*.txt")}

    async def ask(self, prompt, schema, data):
        if not self.client:
            raise AppError(
                "MODEL_UNAVAILABLE",
                "AI is not configured. Set GOOGLE_API_KEY and MODEL_NAME on the server.",
                503,
            )
        state = budget.get()
        for attempt in range(2):
            if state is None or state["calls"] >= 8:
                raise AppError("MODEL_BUDGET", "The response reached its model-call budget.", 502, True)
            state["calls"] += 1
            self.store.charge("model:day", self.settings.daily_model_calls, 86400)
            try:
                response = await asyncio.wait_for(
                    self.client.with_structured_output(
                        schema, method="json_schema", include_raw=True
                    ).ainvoke(
                        [
                            ("system", self.prompts["policy"] + "\n" + self.prompts[prompt]),
                            ("human", json.dumps(data)),
                        ]
                    ),
                    timeout=15,
                )
                if response.get("parsing_error") or response.get("parsed") is None:
                    raise ValueError("Invalid structured response")
                raw = response.get("raw")
                log.info(
                    "model_call prompt=%s model=%s usage=%s",
                    prompt,
                    self.settings.model_name,
                    getattr(raw, "usage_metadata", None),
                )
                parsed = response["parsed"]
                return parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Never include provider response bodies, input, keys, or endpoints in public errors/logs.
                code = getattr(exc, "code", None) or getattr(getattr(exc, "__cause__", None), "code", None)
                log.warning("provider_failure type=%s status=%s", type(exc).__name__, code)
                if code == 429 or "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    raise AppError(
                        "MODEL_RATE_LIMIT",
                        "The AI provider's rate limit was reached. Please wait a minute and retry.",
                        429,
                        True,
                    ) from None
                if code == 404 or "404" in str(exc):
                    raise AppError(
                        "MODEL_UNAVAILABLE", "The configured AI model is unavailable for this account.", 503
                    ) from None
                transient = (
                    code in {408, 500, 502, 503, 504}
                    or isinstance(exc, (TimeoutError, ConnectionError))
                    or any(
                        word in type(exc).__name__.lower()
                        for word in ("timeout", "unavailable", "resourceexhausted")
                    )
                )
                if transient and attempt == 0:
                    continue
                raise AppError(
                    "MODEL_FAILED",
                    "The AI provider could not complete this response. Please retry.",
                    502,
                    True,
                ) from None
