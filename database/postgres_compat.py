"""Small psycopg adapter for the SQL patterns used by EduPilot's current data layer.

This keeps the desktop app's existing SQLite-shaped queries working against
PostgreSQL while the schema is migrated to a shared repository/service layer.
It is not intended to replace explicit, versioned PostgreSQL migrations long term.
"""
from __future__ import annotations

import re


_INSERT_TABLE = re.compile(r"^\s*INSERT\s+(?:OR\s+(?:IGNORE|REPLACE)\s+)?INTO\s+([a-zA-Z_][\w]*)", re.I)
# These tables use natural/text primary keys and have no generated `id`.
_TABLES_WITHOUT_GENERATED_ID = {"app_settings", "local_settings", "stored_files", "faculty_profiles"}


def _translate(sql: str) -> tuple[str, str | None]:
    """Translate the subset of SQLite SQL syntax currently used by EduPilot."""
    statement = sql.strip()
    pragma = re.fullmatch(r"PRAGMA\s+user_version(?:\s*=\s*(\d+))?", statement, re.I)
    if pragma:
        version = pragma.group(1) or "0"
        return f"SELECT {version} AS user_version", None
    if re.match(r"PRAGMA\s+(?:foreign_keys|busy_timeout)", statement, re.I):
        return "SELECT 1", None

    statement = statement.replace("?", "%s")
    statement = re.sub(
        r"\b(id)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        r"\1 BIGSERIAL PRIMARY KEY", statement, flags=re.I,
    )
    statement = re.sub(r"\bDEFAULT\s+CURRENT_TIMESTAMP\b", "DEFAULT (CURRENT_TIMESTAMP::text)", statement, flags=re.I)
    statement = re.sub(r"\bCURRENT_TIMESTAMP\b(?!\s*::text)", "CURRENT_TIMESTAMP::text", statement, flags=re.I)
    statement = re.sub(r"room\s*=\s*(%s)\s+COLLATE\s+NOCASE", r"LOWER(room) = LOWER(\1)", statement, flags=re.I)
    statement = re.sub(r"datetime\('now',\s*'-90 days'\)", "(CURRENT_TIMESTAMP - INTERVAL '90 days')::text", statement, flags=re.I)
    statement = re.sub(r"date\('now',\s*'localtime'\)", "CURRENT_DATE", statement, flags=re.I)
    statement = re.sub(r"date\(([^,()]+),\s*'localtime'\)", r"(\1)::date", statement, flags=re.I)

    ignore = bool(re.match(r"\s*INSERT\s+OR\s+IGNORE\s+INTO\b", statement, re.I))
    replace = bool(re.match(r"\s*INSERT\s+OR\s+REPLACE\s+INTO\b", statement, re.I))
    statement = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", statement, flags=re.I)
    statement = re.sub(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", "INSERT INTO", statement, flags=re.I)

    if replace:
        statement = re.sub(r"\s*;?\s*$", " ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value", statement)
    elif ignore:
        statement = re.sub(r"\s*;?\s*$", " ON CONFLICT DO NOTHING", statement)
    return statement, ("insert" if _INSERT_TABLE.match(statement) else None)


class PostgresCursor:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor
        self._lastrowid = None

    def execute(self, sql, parameters=()):
        statement, kind = _translate(sql)
        match = _INSERT_TABLE.match(statement)
        table = match.group(1).lower() if match else ""
        # Preserve sqlite cursor.lastrowid used by the app. Tables with a
        # generated integer id return it directly from PostgreSQL.
        if (kind == "insert" and table not in _TABLES_WITHOUT_GENERATED_ID
                and not re.search(r"\bRETURNING\b", statement, re.I)):
            statement = re.sub(r"\s*;?\s*$", " RETURNING id", statement)
        self._cursor.execute(statement, parameters)
        self._lastrowid = None
        if (kind == "insert" and table not in _TABLES_WITHOUT_GENERATED_ID
                and re.search(r"\bRETURNING\s+id\s*$", statement, re.I)):
            row = self._cursor.fetchone()
            self._lastrowid = row[0] if row else None
        return self

    def executemany(self, sql, seq_of_parameters):
        statement, _ = _translate(sql)
        self._cursor.executemany(statement, seq_of_parameters)
        self._lastrowid = None
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class PostgresConnection:
    def __init__(self, raw_connection):
        self._connection = raw_connection

    def cursor(self):
        return PostgresCursor(self._connection.cursor())

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()
