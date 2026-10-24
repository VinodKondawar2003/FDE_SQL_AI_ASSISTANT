import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager

from backend.app.errors import AppError

WEEK = 7 * 86400


def uid():
    return str(uuid.uuid4())


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


SCHEMA = """
            CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
                csrf TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations(
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS turns(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                request_id TEXT NOT NULL, payload_hash TEXT NOT NULL, user_text TEXT NOT NULL,
                mode TEXT NOT NULL, status TEXT NOT NULL, response TEXT, created REAL NOT NULL,
                UNIQUE(conversation_id,request_id));
            CREATE TABLE IF NOT EXISTS artifacts(
                id TEXT PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                sql TEXT NOT NULL, hash TEXT NOT NULL, schema_version TEXT NOT NULL, validator_version TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS executions(
                id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
                request_id TEXT NOT NULL, result TEXT NOT NULL, expires REAL NOT NULL,
                UNIQUE(artifact_id,request_id));
            CREATE TABLE IF NOT EXISTS quotas(
                bucket TEXT PRIMARY KEY, used INTEGER NOT NULL, expires REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_turns_conversation ON turns(conversation_id,created);
"""


class Store:
    distributed = False

    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as con:
            con.executescript("PRAGMA journal_mode=WAL;" + SCHEMA)

    @contextmanager
    def db(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def create_session(self):
        token, csrf, session_id = secrets.token_urlsafe(32), secrets.token_urlsafe(32), uid()
        expiry = time.time() + WEEK
        with self.db() as con:
            con.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)", (session_id, token_hash(token), csrf, expiry)
            )
        return token, {"id": session_id, "csrf": csrf, "expires": expiry}

    def session(self, token):
        with self.db() as con:
            row = con.execute(
                "SELECT * FROM sessions WHERE token_hash=? AND expires>?",
                (token_hash(token or ""), time.time()),
            ).fetchone()
            if not row:
                raise AppError("SESSION_EXPIRED", "Your session expired. Start a new session.", 401)
            con.execute("UPDATE sessions SET expires=? WHERE id=?", (time.time() + WEEK, row["id"]))
            return dict(row)

    def conversation(self, cid, sid):
        with self.db() as con:
            row = con.execute(
                "SELECT * FROM conversations WHERE id=? AND session_id=?", (cid, sid)
            ).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "This conversation is not available.", 404)
        return dict(row)

    def create_conversation(self, sid, title):
        cid, now = uid(), time.time()
        with self.db() as con:
            con.execute("INSERT INTO conversations VALUES (?,?,?,?,?)", (cid, sid, title, now, now))
        return self.conversation(cid, sid)

    def conversations(self, sid, cursor=0, limit=50):
        with self.db() as con:
            rows = con.execute(
                "SELECT * FROM conversations WHERE session_id=? ORDER BY updated DESC,id LIMIT ? OFFSET ?",
                (sid, limit + 1, cursor),
            ).fetchall()
        return {
            "items": [dict(r) for r in rows[:limit]],
            "next_cursor": cursor + limit if len(rows) > limit else None,
        }

    def history(self, cid, cursor=0, limit=50):
        with self.db() as con:
            rows = con.execute(
                "SELECT * FROM turns WHERE conversation_id=? ORDER BY created DESC,id DESC LIMIT ? OFFSET ?",
                (cid, limit + 1, cursor),
            ).fetchall()
        items = [
            {
                "id": r["id"],
                "message": r["user_text"],
                "mode": r["mode"],
                "created_at": r["created"],
                "status": r["status"],
                "response": json.loads(r["response"]) if r["response"] else None,
            }
            for r in rows[:limit]
        ]
        return {"items": list(reversed(items)), "next_cursor": cursor + limit if len(rows) > limit else None}

    def begin_turn(self, cid, request_id, message, mode):
        fingerprint = token_hash(json.dumps([message, mode]))
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute(
                "SELECT * FROM turns WHERE conversation_id=? AND request_id=?", (cid, request_id)
            ).fetchone()
            if existing:
                if existing["payload_hash"] != fingerprint:
                    raise AppError("REQUEST_CONFLICT", "This request ID was used for another message.", 409)
                if existing["status"] == "processing":
                    raise AppError("TURN_BUSY", "This request is still being processed.", 409, True)
                return existing["id"], json.loads(existing["response"])
            if con.execute(
                "SELECT 1 FROM turns WHERE conversation_id=? AND status='processing'", (cid,)
            ).fetchone():
                raise AppError(
                    "TURN_BUSY", "Wait for the current response before sending another message.", 409, True
                )
            tid, now = uid(), time.time()
            con.execute(
                "INSERT INTO turns VALUES (?,?,?,?,?,?,?,?,?)",
                (tid, cid, request_id, fingerprint, message, mode, "processing", None, now),
            )
            con.execute(
                "UPDATE conversations SET updated=?,title=CASE WHEN title='New conversation' THEN ? ELSE title END WHERE id=?",
                (now, message[:60], cid),
            )
        return tid, None

    def complete(self, tid, response, validator_version):
        from backend.app.sql.service import digest

        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            if response.get("sql"):
                q = response["sql"]
                con.execute(
                    "INSERT INTO artifacts VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                    (
                        q["artifact_id"],
                        tid,
                        response["conversation_id"],
                        q["text"],
                        digest(q["text"]),
                        q["schema_version"],
                        validator_version,
                    ),
                )
            con.execute(
                "UPDATE turns SET status=?,response=? WHERE id=?",
                (response["status"], json.dumps(response), tid),
            )

    def pending(self, cid=None):
        with self.db() as con:
            if cid is not None:
                return [
                    dict(r)
                    for r in con.execute(
                        "SELECT * FROM turns WHERE conversation_id=? AND status='processing'", (cid,)
                    )
                ]
            return [dict(r) for r in con.execute("SELECT * FROM turns WHERE status='processing'")]

    def artifact(self, aid, sid):
        with self.db() as con:
            row = con.execute(
                """SELECT a.* FROM artifacts a JOIN conversations c ON a.conversation_id=c.id
                                 WHERE a.id=? AND c.session_id=?""",
                (aid, sid),
            ).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "This query is not available.", 404)
        return dict(row)

    def execution(self, eid, sid):
        with self.db() as con:
            row = con.execute(
                """SELECT e.* FROM executions e JOIN artifacts a ON e.artifact_id=a.id
                                 JOIN conversations c ON a.conversation_id=c.id WHERE e.id=? AND c.session_id=?""",
                (eid, sid),
            ).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "This result is not available.", 404)
        if row["expires"] <= time.time():
            raise AppError("RESULT_EXPIRED", "This result has expired. Run the query again.", 410)
        return json.loads(row["result"])

    def previous_execution(self, aid, request_id):
        with self.db() as con:
            row = con.execute(
                "SELECT * FROM executions WHERE artifact_id=? AND request_id=?", (aid, request_id)
            ).fetchone()
        if row and row["expires"] <= time.time():
            raise AppError("RESULT_EXPIRED", "This result expired. Use a new execution request.", 410)
        return json.loads(row["result"]) if row else None

    def save_execution(self, aid, request_id, result):
        result = {**result, "execution_id": uid(), "artifact_id": aid, "expires_at": time.time() + 3600}
        with self.db() as con:
            con.execute(
                "INSERT INTO executions VALUES (?,?,?,?,?)",
                (result["execution_id"], aid, request_id, json.dumps(result), result["expires_at"]),
            )
        return result

    def delete(self, cid, sid):
        self.conversation(cid, sid)
        with self.db() as con:
            con.execute("DELETE FROM conversations WHERE id=?", (cid,))

    def charge(self, key, limit, seconds=60):
        now = time.time()
        bucket = f"{key}:{int(now // seconds)}"
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT used FROM quotas WHERE bucket=?", (bucket,)).fetchone()
            if row and row["used"] >= limit:
                raise AppError(
                    "RATE_LIMIT", "The demo request limit has been reached. Try again later.", 429, True
                )
            con.execute(
                "INSERT INTO quotas VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET used=quotas.used+1",
                (bucket, now + seconds),
            )

    def cleanup(self):
        now = time.time()
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            expired = [
                r["id"]
                for r in con.execute(
                    """SELECT c.id FROM conversations c JOIN sessions s ON c.session_id=s.id
                WHERE (s.expires<? OR c.updated<?) AND NOT EXISTS(
                SELECT 1 FROM turns t WHERE t.conversation_id=c.id AND t.status='processing')""",
                    (now, now - WEEK),
                )
            ]
            for cid in expired:
                con.execute("DELETE FROM conversations WHERE id=?", (cid,))
            con.execute(
                "DELETE FROM sessions WHERE expires<? AND id NOT IN (SELECT session_id FROM conversations)",
                (now,),
            )
            # Keep expiry tombstones for 410, but purge all result data after one hour.
            con.execute("UPDATE executions SET result='{}' WHERE expires<?", (now,))
            con.execute("DELETE FROM quotas WHERE expires<?", (now,))
        return expired
