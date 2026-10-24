# Four-minute local demo

Use the actual application and configured Gemini model. Automated browser-test screenshots use a test-only model and are labeled as test evidence; do not present them as live-model proof.

0:00–0:30 — Open Querycraft. Show the six-table schema and explain that all data is synthetic and queries are read-only.
0:30–1:15 — Ask for customer_id and first_name for all customers. Inspect SQL and its explanation, then Run. Show 80 rows.
1:15–1:50 — Ask “Only those from California.” Show the preserved projection and new filter; Run gives 40 rows. Download CSV.
1:50–2:30 — Debug a misspelled SELECT and explain the correction. Optimize a query containing a removable unique-parent join.
2:30–3:15 — Ask to delete customers and then an unrelated sports question. Both must refuse. Ask about employees hired after January 2024 and show clarification.
3:15–4:00 — Show history after refresh, the query-plan panel, LangGraph workflow, and tests. State the exact live model and any remaining deployment limitations.

A submitted recording must last 3–5 minutes, use the real provider, and clearly identify a local demonstration if public hosting is still pending.
