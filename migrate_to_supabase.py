"""Move the current SQLite economy data into the Supabase Postgres project."""

from __future__ import annotations

import os
import re
import secrets
import sqlite3
import sys
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

try:
    import psycopg
    from psycopg import sql
except ImportError as error:
    raise SystemExit(
        "먼저 python -m pip install -r requirements.txt 를 실행해 주세요."
    ) from error


ROOT = Path(__file__).resolve().parent
MIGRATION_FILE = ROOT / "supabase" / "migrations" / "20260926015052_create_economy.sql"
ENV_FILE = ROOT / ".env"
TABLES = ("accounts", "shop_items", "inventory")
APP_ROLE = "ple_bot_app"


def read_sqlite_data(path: Path) -> dict[str, list[tuple[object, ...]]]:
    if not path.is_file():
        raise RuntimeError(f"SQLite 데이터베이스 파일을 찾을 수 없습니다: {path}")

    uri_path = quote(str(path.resolve()), safe="/")
    source = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        account_rows = source.execute(
            """SELECT guild_id, user_id, balance, last_daily
               FROM accounts ORDER BY guild_id, user_id"""
        ).fetchall()
        shop_rows = source.execute(
            """SELECT guild_id, item_name, description, price, stock, role_id
               FROM shop_items ORDER BY guild_id, item_name"""
        ).fetchall()
        inventory_rows = source.execute(
            """SELECT guild_id, user_id, item_name, quantity, cost_basis
               FROM inventory ORDER BY guild_id, user_id, item_name"""
        ).fetchall()
    finally:
        source.close()

    return {
        "accounts": [tuple(row) for row in account_rows],
        "shop_items": [tuple(row) for row in shop_rows],
        "inventory": [tuple(row) for row in inventory_rows],
    }


def _dsn_username(dsn: str) -> str:
    return unquote(urlsplit(dsn).username or "")


def _is_app_dsn(dsn: str) -> bool:
    username = _dsn_username(dsn)
    return username == APP_ROLE or username.startswith(APP_ROLE + ".")


def _same_target(first_dsn: str, second_dsn: str) -> bool:
    first = urlsplit(first_dsn)
    second = urlsplit(second_dsn)
    first_host = (first.hostname or "").lower()
    second_host = (second.hostname or "").lower()

    if first_host != second_host or first.path != second.path:
        return False
    if first_host.endswith(".pooler.supabase.com"):
        first_project = _dsn_username(first_dsn).split(".", 1)
        second_project = _dsn_username(second_dsn).split(".", 1)
        return (
            len(first_project) == 2
            and len(second_project) == 2
            and first_project[1] == second_project[1]
        )
    return True


def _make_app_dsn(admin_dsn: str, password: str) -> str:
    parts = urlsplit(admin_dsn)
    admin_username = _dsn_username(admin_dsn)
    username = APP_ROLE
    if "." in admin_username:
        username = f"{APP_ROLE}.{admin_username.split('.', 1)[1]}"

    host_and_port = parts.netloc.rsplit("@", 1)[-1]
    credentials = f"{quote(username, safe='.') }:{quote(password, safe='-_.~')}@"
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    return urlunsplit(
        (
            parts.scheme,
            credentials + host_and_port,
            parts.path,
            urlencode(query),
            "",
        )
    )


def _save_env_value(key: str, value: str) -> None:
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    encoded_value = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    replacement = f"{key}={encoded_value}"
    for index, line in enumerate(lines):
        if line.strip().startswith(key + "="):
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    ENV_FILE.write_text("\n".join(lines) + "\n")


def _remove_env_value(key: str) -> None:
    if not ENV_FILE.exists():
        return
    lines = ENV_FILE.read_text().splitlines()
    kept = [line for line in lines if not line.strip().startswith(key + "=")]
    ENV_FILE.write_text("\n".join(kept) + ("\n" if kept else ""))


def _load_migration_statements() -> list[str]:
    if not MIGRATION_FILE.is_file():
        raise RuntimeError(f"마이그레이션 파일을 찾을 수 없습니다: {MIGRATION_FILE}")
    return [
        statement.strip()
        for statement in MIGRATION_FILE.read_text().split(";")
        if statement.strip()
    ]


def migrate() -> None:
    load_dotenv(ENV_FILE)
    admin_dsn = os.getenv("SUPABASE_ADMIN_DATABASE_URL", "").strip()
    if not admin_dsn:
        raise RuntimeError(
            ".env에 SUPABASE_ADMIN_DATABASE_URL을 설정해 주세요. "
            "Supabase 대시보드 Connect의 Direct 또는 Session pooler 주소를 사용하세요."
        )

    if urlsplit(admin_dsn).port == 6543:
        raise RuntimeError(
            "초기 이전에는 Transaction pooler 대신 Direct 또는 Session pooler를 사용하세요."
        )

    database_path = Path(os.getenv("DATABASE_PATH", "data/economy.sqlite3"))
    if not database_path.is_absolute():
        database_path = ROOT / database_path
    data = read_sqlite_data(database_path)
    current_app_dsn = os.getenv("DATABASE_URL", "").strip()
    app_dsn: str

    with psycopg.connect(
        admin_dsn, connect_timeout=10, sslmode="require"
    ) as connection:
        present = connection.execute(
            """SELECT
                   to_regclass('public.accounts'),
                   to_regclass('public.shop_items'),
                   to_regclass('public.inventory')"""
        ).fetchone()
        if any(table is not None for table in present):
            raise RuntimeError(
                "Supabase에 대상 테이블이 이미 있습니다. 기존 테이블을 덮어쓰지 않도록 "
                "이전 작업을 중단했습니다."
            )

        role_exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,)
        ).fetchone() is not None

        if role_exists:
            if not current_app_dsn or not _is_app_dsn(current_app_dsn):
                raise RuntimeError(
                    "ple_bot_app 역할이 이미 있습니다. 기존 역할의 DATABASE_URL을 "
                    ".env에 설정한 뒤 다시 실행해 주세요."
                )
            if not _same_target(admin_dsn, current_app_dsn):
                raise RuntimeError(
                    "DATABASE_URL과 SUPABASE_ADMIN_DATABASE_URL의 프로젝트가 다릅니다."
                )
            app_dsn = current_app_dsn
        else:
            if current_app_dsn and not _is_app_dsn(current_app_dsn):
                raise RuntimeError(
                    "DATABASE_URL이 이미 다른 역할로 설정되어 있어 덮어쓰지 않았습니다."
                )
            app_password = (
                unquote(urlsplit(current_app_dsn).password)
                if current_app_dsn
                else secrets.token_urlsafe(36)
            )
            app_dsn = _make_app_dsn(admin_dsn, app_password)
            _save_env_value("DATABASE_URL", app_dsn)
            connection.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(APP_ROLE), sql.Literal(app_password)
                )
            )

        statements = _load_migration_statements()
        for statement in statements:
            connection.execute(statement)

        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO public.accounts
                   (guild_id, user_id, balance, last_daily)
                   VALUES (%s, %s, %s, %s)""",
                data["accounts"],
            )
            cursor.executemany(
                """INSERT INTO public.shop_items
                   (guild_id, item_name, description, price, stock, role_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                data["shop_items"],
            )
            cursor.executemany(
                """INSERT INTO public.inventory
                   (guild_id, user_id, item_name, quantity, cost_basis)
                   VALUES (%s, %s, %s, %s, %s)""",
                data["inventory"],
            )

        uploaded_counts = {
            table: connection.execute(
                f"SELECT count(*) FROM public.{table}"
            ).fetchone()[0]
            for table in TABLES
        }
        expected_counts = {table: len(data[table]) for table in TABLES}
        if uploaded_counts != expected_counts:
            raise RuntimeError("이전한 행 수가 SQLite 원본과 달라 작업을 취소했습니다.")

    with psycopg.connect(
        app_dsn, connect_timeout=10, sslmode="require"
    ) as app_connection:
        visible_counts = {
            table: app_connection.execute(
                f"SELECT count(*) FROM public.{table}"
            ).fetchone()[0]
            for table in TABLES
        }
    if visible_counts != expected_counts:
        raise RuntimeError(
            "앱 전용 DB 계정으로 이전 결과를 확인하지 못했습니다. "
            "Supabase 권한 설정을 확인해 주세요."
        )

    _remove_env_value("SUPABASE_ADMIN_DATABASE_URL")
    print(
        "Supabase 이전 완료: "
        + ", ".join(f"{table}={visible_counts[table]}" for table in TABLES)
    )
    print("앱 전용 DATABASE_URL을 .env에 저장했습니다.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as error:
        safe_message = re.sub(
            r"(?i)(postgres(?:ql)?://)[^\s@]+@",
            r"\1<redacted>@",
            str(error),
        )
        print(f"Supabase 이전 실패: {safe_message}", file=sys.stderr)
        raise SystemExit(1) from None
