"""Test-only adapter. Not selectable from runtime configuration."""

from backend.app.agent.model import Classification, Candidate, Explanation, Advice


class ScriptedModel:
    def __init__(self, settings=None, store=None):
        self.calls = 0

    async def ask(self, prompt, schema, data):
        self.calls += 1
        text = data["current_message"].lower()
        if schema is Classification:
            if any(s in text for s in ["fifa", "politics", "poem", "ignore", "delete", "drop"]):
                return Classification(intent="refuse", in_scope=False)
            return Classification(intent="debug" if "selec " in text else "generate", in_scope=True)
        if schema is Candidate:
            if "repair" == prompt:
                return Candidate(
                    kind="sql",
                    sql="SELECT * FROM customers",
                    issues=["Corrected the misspelled query keyword."],
                )
            if "invalid" in text:
                return Candidate(kind="sql", sql="SELECT made_up FROM customers")
            if "selec " in text:
                return Candidate(kind="sql", sql="SELEC * FROM customers")
            if "california" in text or "only ca" in text:
                return Candidate(kind="sql", sql="SELECT * FROM customers WHERE state='CA'")
            if "sort" in text or "last name" in text:
                return Candidate(kind="sql", sql=data["last_validated_sql"] + " ORDER BY last_name")
            if "february" in text:
                return Candidate(kind="sql", sql="SELECT * FROM employees WHERE hire_date >= '2024-02-01'")
            return Candidate(kind="sql", sql="SELECT * FROM customers")
        if schema is Explanation:
            return Explanation(
                summary="Retrieves the requested records from the sample database.",
                steps=["Applies the specified filters."],
                referenced_identifiers=["customers"],
            )
        if schema is Advice:
            return Advice(suggestions=["Compare the query plan before changing indexes."])
