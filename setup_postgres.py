"""Create the local EduPilot PostgreSQL database and save its private connection URL."""
from __future__ import annotations

import getpass
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql


if os.environ.get("EDUPILOT_DATA_DIR"):
    APP_DATA_DIR = Path(os.environ["EDUPILOT_DATA_DIR"]).expanduser()
elif sys.platform == "win32":
    APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "EduPilot"
elif sys.platform == "darwin":
    APP_DATA_DIR = Path.home() / "Library" / "Application Support" / "EduPilot"
else:
    APP_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "edupilot"

DB_NAME = "edupilot"
APP_ROLE = "edupilot_app"
CONFIG_FILE = APP_DATA_DIR / "postgres_url.txt"


def main() -> int:
    print("EduPilot PostgreSQL setup")
    print("Enter the postgres administrator password you chose during PostgreSQL installation.")
    admin_password = getpass.getpass("PostgreSQL postgres password (input hidden): ")
    app_password = secrets.token_urlsafe(32)

    try:
        with psycopg.connect(
            host="localhost", port=5432, dbname="postgres", user="postgres",
            password=admin_password, connect_timeout=5, autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
                if cursor.fetchone():
                    cursor.execute(
                        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                            sql.Identifier(APP_ROLE), sql.Literal(app_password)
                        )
                    )
                else:
                    cursor.execute(
                        sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                            sql.Identifier(APP_ROLE), sql.Literal(app_password)
                        )
                    )
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
                if cursor.fetchone():
                    cursor.execute(
                        sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                            sql.Identifier(DB_NAME), sql.Identifier(APP_ROLE)
                        )
                    )
                else:
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {} OWNER {}").format(
                            sql.Identifier(DB_NAME), sql.Identifier(APP_ROLE)
                        )
                    )

        connection_url = (
            f"postgresql://{quote(APP_ROLE)}:{quote(app_password)}@localhost:5432/{quote(DB_NAME)}"
        )
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(connection_url + "\n", encoding="utf-8")
        try:
            CONFIG_FILE.chmod(0o600)
        except OSError:
            pass  # Windows relies on the user's Local AppData directory ACL.

        with psycopg.connect(connection_url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                database, user = cursor.fetchone()
        print(f"Connected successfully to database '{database}' as '{user}'.")
        print("The connection is saved in your EduPilot application-data folder.")
        print("Start EduPilot; it will create its tables and demo accounts in PostgreSQL.")
        return 0
    except Exception as error:
        print(f"Setup could not connect or configure PostgreSQL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
