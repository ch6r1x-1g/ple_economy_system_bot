"""SQLite or Supabase Postgres-backed, per-server point balances."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class _StoreConnection:
    """Adapt store SQL and route table names to one Discord server."""

    _TABLES = (
        "accounts",
        "shop_items",
        "inventory",
        "shared_accounts",
        "voice_activity",
    )

    def __init__(
        self, connection: Any, *, guild_id: int | None, is_postgres: bool
    ) -> None:
        self._connection = connection
        self._guild_id = guild_id
        self._is_postgres = is_postgres

    def __enter__(self) -> "_StoreConnection":
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        return self._connection.__exit__(exc_type, exc, traceback)

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> Any:
        if self._guild_id is not None:
            for table in self._TABLES:
                query = re.sub(
                    rf"\b{table}\b",
                    f"{table}_{self._guild_id}",
                    query,
                    flags=re.IGNORECASE,
                )

        if self._is_postgres:
            if query.lstrip().upper().startswith("PRAGMA "):
                return None

            if query.lstrip().upper().startswith("BEGIN IMMEDIATE"):
                # Psycopg opens a transaction on the first statement when autocommit is off.
                return None

            if "INSERT OR IGNORE INTO" in query.upper():
                query = query.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
                query = query.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

            query = query.replace("COLLATE NOCASE", "")
            query = query.replace("?", "%s")
        return self._connection.execute(query, parameters)


class InsufficientFunds(Exception):
    def __init__(self, balance: int, required: int | None = None) -> None:
        self.balance = balance
        self.required = required
        super().__init__("insufficient funds")


class InsufficientSharedFunds(Exception):
    def __init__(self, balance: int) -> None:
        self.balance = balance
        super().__init__("insufficient shared account funds")


class ShopItemNotFound(Exception):
    pass


class ItemNotInInventory(Exception):
    pass


class InsufficientInventory(Exception):
    def __init__(self, available: int) -> None:
        self.available = available
        super().__init__("not enough items in inventory")


class ShopLimitReached(Exception):
    pass


class ShopItemNameTaken(Exception):
    pass


class OutOfStock(Exception):
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining
        super().__init__("out of stock")


@dataclass(frozen=True)
class ShopItem:
    name: str
    description: str
    price: int
    stock: int | None
    role_id: int | None


class EconomyStore:
    def __init__(
        self,
        database_path: str,
        database_url: str | None = None,
        guild_ids: tuple[int, ...] = (),
    ) -> None:
        self.database_path = Path(database_path)
        self.database_url = database_url
        self.is_postgres = bool(database_url)
        self.guild_ids = tuple(guild_ids)

    def _connect(self, guild_id: int | None = None) -> Any:
        if guild_id is not None and self.guild_ids and guild_id not in self.guild_ids:
            raise RuntimeError(f"GUILD_IDS에 등록되지 않은 Discord 서버입니다: {guild_id}")
        table_guild_id = guild_id if self.guild_ids else None

        if self.database_url:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as error:
                raise RuntimeError(
                    "Supabase를 사용하려면 requirements.txt의 psycopg를 설치해 주세요."
                ) from error

            connection = psycopg.connect(
                self.database_url,
                connect_timeout=10,
                row_factory=dict_row,
                sslmode="require",
            )
            return _StoreConnection(
                connection, guild_id=table_guild_id, is_postgres=True
            )

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return _StoreConnection(
            connection, guild_id=table_guild_id, is_postgres=False
        )

    def _for_update(self) -> str:
        return " FOR UPDATE" if self.is_postgres else ""

    @staticmethod
    def _ensure_account(
        connection: Any, guild_id: int, user_id: int
    ) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO accounts (guild_id, user_id, balance)
               VALUES (?, ?, 0)""",
            (guild_id, user_id),
        )

    @staticmethod
    def _initialize_voice_activity_table(connection: Any, table_name: str) -> None:
        connection.execute(
            f"""CREATE TABLE IF NOT EXISTS {table_name} (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                accrued_units INTEGER NOT NULL DEFAULT 0
                    CHECK (accrued_units >= 0),
                PRIMARY KEY (guild_id, user_id)
            )"""
        )
        columns = {
            str(row["name"])
            for row in connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
        }
        if "accrued_units" not in columns:
            connection.execute(
                f"""ALTER TABLE {table_name}
                    ADD COLUMN accrued_units INTEGER NOT NULL DEFAULT 0
                    CHECK (accrued_units >= 0)"""
            )
        if "accrued_seconds" in columns:
            # Older builds kept partial hours as seconds at the 100-points/hour rate.
            connection.execute(
                f"""UPDATE {table_name}
                    SET accrued_units = accrued_seconds * 100
                    WHERE accrued_seconds > 0 AND accrued_units = 0"""
            )
            connection.execute(
                f"UPDATE {table_name} SET accrued_seconds = 0 WHERE accrued_seconds > 0"
            )

    @staticmethod
    def _ensure_shared_account(connection: Any, guild_id: int) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO shared_accounts (guild_id, balance)
               VALUES (?, 0)""",
            (guild_id,),
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            if self.is_postgres:
                if self.guild_ids:
                    for guild_id in self.guild_ids:
                        names = tuple(
                            f"{table}_{guild_id}"
                            for table in _StoreConnection._TABLES
                        )
                        found = connection.execute(
                            "SELECT " + ", ".join(
                                f"to_regclass('public.{name}') AS t{index}"
                                for index, name in enumerate(names)
                            ) + ", EXISTS (SELECT 1 FROM information_schema.columns "
                                f"WHERE table_schema = 'public' AND table_name = "
                                f"'voice_activity_{guild_id}' AND column_name = "
                                "'accrued_units') AS voice_units"
                        ).fetchone()
                        missing = [
                            name
                            for index, name in enumerate(names)
                            if found[f"t{index}"] is None
                        ]
                        if not found["voice_units"]:
                            missing.append(
                                f"voice_activity_{guild_id}.accrued_units"
                            )
                        if missing:
                            raise RuntimeError(
                                "Supabase 서버별 테이블이 없습니다: "
                                + ", ".join(missing)
                                + ". supabase/migrations의 서버별 경제 테이블 및 "
                                "20260927120000_create_voice_activity.sql 파일을 "
                                "Supabase SQL Editor에서 적용해 주세요."
                            )
                    return

                row = connection.execute(
                    """SELECT
                           to_regclass('public.accounts') AS accounts,
                           to_regclass('public.shop_items') AS shop_items,
                           to_regclass('public.inventory') AS inventory,
                           to_regclass('public.shared_accounts') AS shared_accounts,
                           to_regclass('public.voice_activity') AS voice_activity,
                           EXISTS (
                               SELECT 1 FROM information_schema.columns
                               WHERE table_schema = 'public'
                                 AND table_name = 'voice_activity'
                                 AND column_name = 'accrued_units'
                           ) AS voice_units"""
                ).fetchone()
                missing_base_tables = [
                    table for table in ("accounts", "shop_items", "inventory")
                    if row[table] is None
                ]
                if missing_base_tables:
                    raise RuntimeError(
                        "Supabase 테이블이 없습니다. 먼저 "
                        "python migrate_to_supabase.py를 실행해 주세요."
                    )
                if row["shared_accounts"] is None:
                    raise RuntimeError(
                        "Supabase 공동 계좌 테이블이 없습니다. "
                        "supabase/migrations의 create_shared_accounts SQL을 "
                        "Supabase SQL Editor에서 적용해 주세요."
                    )
                if row["voice_activity"] is None:
                    raise RuntimeError(
                        "Supabase 보이스 활동 테이블이 없습니다. "
                        "supabase/migrations/20260927120000_create_voice_activity.sql "
                        "파일을 Supabase SQL Editor에서 적용해 주세요."
                    )
                if not row["voice_units"]:
                    raise RuntimeError(
                        "Supabase 보이스 활동 테이블을 최신 구조로 바꾸려면 "
                        "supabase/migrations/20260927120000_create_voice_activity.sql "
                        "파일을 SQL Editor에서 다시 실행해 주세요."
                    )
                return

            connection.execute("PRAGMA journal_mode = WAL")
            if self.guild_ids:
                for guild_id in self.guild_ids:
                    connection.execute(
                        f"""CREATE TABLE IF NOT EXISTS accounts_{guild_id} (
                            guild_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
                            last_daily TEXT,
                            PRIMARY KEY (guild_id, user_id)
                        )"""
                    )
                    connection.execute(
                        f"""CREATE TABLE IF NOT EXISTS shop_items_{guild_id} (
                            guild_id INTEGER NOT NULL,
                            item_name TEXT NOT NULL COLLATE NOCASE,
                            description TEXT NOT NULL DEFAULT '',
                            price INTEGER NOT NULL CHECK (price > 0),
                            stock INTEGER CHECK (stock IS NULL OR stock >= 0),
                            role_id INTEGER,
                            PRIMARY KEY (guild_id, item_name)
                        )"""
                    )
                    connection.execute(
                        f"""CREATE TABLE IF NOT EXISTS inventory_{guild_id} (
                            guild_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            item_name TEXT NOT NULL COLLATE NOCASE,
                            quantity INTEGER NOT NULL CHECK (quantity > 0),
                            cost_basis INTEGER NOT NULL DEFAULT 0 CHECK (cost_basis >= 0),
                            PRIMARY KEY (guild_id, user_id, item_name)
                        )"""
                    )
                    connection.execute(
                        f"""CREATE TABLE IF NOT EXISTS shared_accounts_{guild_id} (
                            guild_id INTEGER NOT NULL PRIMARY KEY,
                            balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0)
                        )"""
                    )
                    self._initialize_voice_activity_table(
                        connection, f"voice_activity_{guild_id}"
                    )
                return

            connection.execute(
                """CREATE TABLE IF NOT EXISTS accounts (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
                    last_daily TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS shared_accounts (
                    guild_id INTEGER NOT NULL PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0)
                )"""
            )
            self._initialize_voice_activity_table(connection, "voice_activity")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS shop_items (
                    guild_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL COLLATE NOCASE,
                    description TEXT NOT NULL DEFAULT '',
                    price INTEGER NOT NULL CHECK (price > 0),
                    stock INTEGER CHECK (stock IS NULL OR stock >= 0),
                    PRIMARY KEY (guild_id, item_name)
                )"""
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(shop_items)").fetchall()
            }
            if "role_id" not in columns:
                connection.execute("ALTER TABLE shop_items ADD COLUMN role_id INTEGER")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS inventory (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL COLLATE NOCASE,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    cost_basis INTEGER NOT NULL DEFAULT 0 CHECK (cost_basis >= 0),
                    PRIMARY KEY (guild_id, user_id, item_name)
                )"""
            )
            inventory_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(inventory)").fetchall()
            }
            if "cost_basis" not in inventory_columns:
                connection.execute(
                    "ALTER TABLE inventory ADD COLUMN cost_basis INTEGER NOT NULL DEFAULT 0"
                )
            # Older inventory rows did not retain purchase prices. Use the current
            # listing as a one-time estimate when the corresponding product exists.
            connection.execute(
                """UPDATE inventory
                   SET cost_basis = quantity * COALESCE((
                       SELECT price FROM shop_items
                       WHERE shop_items.guild_id = inventory.guild_id
                         AND shop_items.item_name = inventory.item_name
                   ), 0)
                   WHERE cost_basis = 0"""
            )

    def balance(self, guild_id: int, user_id: int) -> int:
        with self._connect(guild_id) as connection:
            self._ensure_account(connection, guild_id, user_id)
            row = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            return int(row["balance"])

    def shared_balance(self, guild_id: int) -> int:
        with self._connect(guild_id) as connection:
            self._ensure_shared_account(connection, guild_id)
            row = connection.execute(
                "SELECT balance FROM shared_accounts WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
            return int(row["balance"])

    def deposit_shared(
        self, guild_id: int, user_id: int, amount: int
    ) -> tuple[int, int]:
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, guild_id, user_id)
            self._ensure_shared_account(connection, guild_id)
            account = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?"
                + self._for_update(),
                (guild_id, user_id),
            ).fetchone()
            shared = connection.execute(
                "SELECT balance FROM shared_accounts WHERE guild_id = ?"
                + self._for_update(),
                (guild_id,),
            ).fetchone()
            account_balance = int(account["balance"])
            shared_balance = int(shared["balance"])
            if account_balance < amount:
                raise InsufficientFunds(account_balance, amount)
            connection.execute(
                "UPDATE accounts SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
                (amount, guild_id, user_id),
            )
            connection.execute(
                "UPDATE shared_accounts SET balance = balance + ? WHERE guild_id = ?",
                (amount, guild_id),
            )
            return account_balance - amount, shared_balance + amount

    def withdraw_shared(
        self, guild_id: int, user_id: int, amount: int
    ) -> tuple[int, int]:
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, guild_id, user_id)
            self._ensure_shared_account(connection, guild_id)
            account = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?"
                + self._for_update(),
                (guild_id, user_id),
            ).fetchone()
            shared = connection.execute(
                "SELECT balance FROM shared_accounts WHERE guild_id = ?"
                + self._for_update(),
                (guild_id,),
            ).fetchone()
            account_balance = int(account["balance"])
            shared_balance = int(shared["balance"])
            if shared_balance < amount:
                raise InsufficientSharedFunds(shared_balance)
            connection.execute(
                "UPDATE shared_accounts SET balance = balance - ? WHERE guild_id = ?",
                (amount, guild_id),
            )
            connection.execute(
                "UPDATE accounts SET balance = balance + ? WHERE guild_id = ? AND user_id = ?",
                (amount, guild_id, user_id),
            )
            return account_balance + amount, shared_balance - amount

    def claim_daily(
        self, guild_id: int, user_id: int, day: str, reward: int
    ) -> tuple[bool, int]:
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, guild_id, user_id)
            row = connection.execute(
                """SELECT balance, last_daily FROM accounts
                   WHERE guild_id = ? AND user_id = ?"""
                + self._for_update(),
                (guild_id, user_id),
            ).fetchone()
            if row["last_daily"] == day:
                return False, int(row["balance"])
            connection.execute(
                """UPDATE accounts SET balance = balance + ?, last_daily = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (reward, day, guild_id, user_id),
            )
            return True, int(row["balance"]) + reward

    def accrue_voice_reward_units(
        self,
        guild_id: int,
        user_id: int,
        reward_units: int,
    ) -> tuple[int, int]:
        """Persist fractional rewards and credit each completed 3,600 units."""
        if reward_units <= 0:
            return 0, self.balance(guild_id, user_id)

        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, guild_id, user_id)
            connection.execute(
                """INSERT OR IGNORE INTO voice_activity
                   (guild_id, user_id, accrued_units) VALUES (?, ?, 0)""",
                (guild_id, user_id),
            )
            activity = connection.execute(
                """SELECT accrued_units FROM voice_activity
                   WHERE guild_id = ? AND user_id = ?""" + self._for_update(),
                (guild_id, user_id),
            ).fetchone()
            total_units = int(activity["accrued_units"]) + reward_units
            reward, remainder = divmod(total_units, 3600)
            connection.execute(
                """UPDATE voice_activity SET accrued_units = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (remainder, guild_id, user_id),
            )
            if reward:
                connection.execute(
                    """UPDATE accounts SET balance = balance + ?
                       WHERE guild_id = ? AND user_id = ?""",
                    (reward, guild_id, user_id),
                )
            balance = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            return reward, int(balance["balance"])

    def transfer(
        self, guild_id: int, sender_id: int, recipient_id: int, amount: int
    ) -> tuple[int, int]:
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, guild_id, sender_id)
            self._ensure_account(connection, guild_id, recipient_id)
            if self.is_postgres:
                for locked_user_id in sorted({sender_id, recipient_id}):
                    connection.execute(
                        """SELECT user_id FROM accounts
                           WHERE guild_id = ? AND user_id = ? FOR UPDATE""",
                        (guild_id, locked_user_id),
                    )
            sender = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?",
                (guild_id, sender_id),
            ).fetchone()
            sender_balance = int(sender["balance"])
            if sender_balance < amount:
                raise InsufficientFunds(sender_balance)
            connection.execute(
                """UPDATE accounts SET balance = balance - ?
                   WHERE guild_id = ? AND user_id = ?""",
                (amount, guild_id, sender_id),
            )
            connection.execute(
                """UPDATE accounts SET balance = balance + ?
                   WHERE guild_id = ? AND user_id = ?""",
                (amount, guild_id, recipient_id),
            )
            recipient = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?",
                (guild_id, recipient_id),
            ).fetchone()
            return sender_balance - amount, int(recipient["balance"])

    def adjust(self, guild_id: int, user_id: int, delta: int) -> int:
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_account(connection, guild_id, user_id)
            row = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?"
                + self._for_update(),
                (guild_id, user_id),
            ).fetchone()
            balance = int(row["balance"])
            if balance + delta < 0:
                raise InsufficientFunds(balance)
            connection.execute(
                """UPDATE accounts SET balance = balance + ?
                   WHERE guild_id = ? AND user_id = ?""",
                (delta, guild_id, user_id),
            )
            return balance + delta

    def set_balance(self, guild_id: int, user_id: int, balance: int) -> None:
        with self._connect(guild_id) as connection:
            self._ensure_account(connection, guild_id, user_id)
            connection.execute(
                "UPDATE accounts SET balance = ? WHERE guild_id = ? AND user_id = ?",
                (balance, guild_id, user_id),
            )

    def list_shop_items(self, guild_id: int, limit: int = 20) -> list[ShopItem]:
        with self._connect(guild_id) as connection:
            rows = connection.execute(
                """SELECT item_name, description, price, stock, role_id FROM shop_items
                   WHERE guild_id = ? ORDER BY item_name COLLATE NOCASE LIMIT ?""",
                (guild_id, limit),
            ).fetchall()
            return [
                ShopItem(
                    name=str(row["item_name"]),
                    description=str(row["description"]),
                    price=int(row["price"]),
                    stock=None if row["stock"] is None else int(row["stock"]),
                    role_id=None if row["role_id"] is None else int(row["role_id"]),
                )
                for row in rows
            ]

    def add_shop_item(
        self,
        guild_id: int,
        name: str,
        description: str,
        price: int,
        stock: int | None,
        role_id: int | None,
    ) -> bool:
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if self.is_postgres:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(?)", (guild_id,)
                )
            existing = connection.execute(
                "SELECT 1 FROM shop_items WHERE guild_id = ? AND item_name = ?",
                (guild_id, name),
            ).fetchone()
            if existing is not None:
                return False
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM shop_items WHERE guild_id = ?",
                (guild_id,),
            ).fetchone()
            if int(count["count"]) >= 20:
                raise ShopLimitReached
            cursor = connection.execute(
                """INSERT INTO shop_items
                   (guild_id, item_name, description, price, stock, role_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (guild_id, name, description, price, stock, role_id),
            )
            return cursor.rowcount == 1

    def remove_shop_item(self, guild_id: int, name: str) -> bool:
        with self._connect(guild_id) as connection:
            cursor = connection.execute(
                "DELETE FROM shop_items WHERE guild_id = ? AND item_name = ?",
                (guild_id, name),
            )
            return cursor.rowcount == 1

    def update_shop_item(
        self,
        guild_id: int,
        name: str,
        *,
        new_name: str | None = None,
        price: int | None = None,
        description: str | None = None,
        stock: int | None = None,
        unlimited_stock: bool = False,
        role_id: int | None = None,
        remove_role: bool = False,
    ) -> ShopItem | None:
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT item_name, description, price, stock, role_id
                   FROM shop_items WHERE guild_id = ? AND item_name = ?"""
                + self._for_update(),
                (guild_id, name),
            ).fetchone()
            if row is None:
                return None

            current_name = str(row["item_name"])
            updated_name = current_name if new_name is None else new_name
            if updated_name != current_name:
                duplicate = connection.execute(
                    """SELECT 1 FROM shop_items
                       WHERE guild_id = ? AND item_name = ? AND item_name <> ?""",
                    (guild_id, updated_name, current_name),
                ).fetchone()
                if duplicate is not None:
                    raise ShopItemNameTaken

                if updated_name.casefold() == current_name.casefold():
                    connection.execute(
                        "UPDATE inventory SET item_name = ? WHERE guild_id = ? AND item_name = ?",
                        (updated_name, guild_id, current_name),
                    )
                else:
                    inventory_rows = connection.execute(
                        """SELECT user_id, quantity, cost_basis FROM inventory
                           WHERE guild_id = ? AND item_name = ?""",
                        (guild_id, current_name),
                    ).fetchall()
                    for inventory_row in inventory_rows:
                        user_id = int(inventory_row["user_id"])
                        quantity = int(inventory_row["quantity"])
                        cost_basis = int(inventory_row["cost_basis"])
                        existing = connection.execute(
                            """SELECT quantity, cost_basis FROM inventory
                               WHERE guild_id = ? AND user_id = ? AND item_name = ?""",
                            (guild_id, user_id, updated_name),
                        ).fetchone()
                        if existing is None:
                            connection.execute(
                                """UPDATE inventory SET item_name = ?
                                   WHERE guild_id = ? AND user_id = ? AND item_name = ?""",
                                (updated_name, guild_id, user_id, current_name),
                            )
                        else:
                            connection.execute(
                                """UPDATE inventory
                                   SET quantity = quantity + ?, cost_basis = cost_basis + ?
                                   WHERE guild_id = ? AND user_id = ? AND item_name = ?""",
                                (quantity, cost_basis, guild_id, user_id, updated_name),
                            )
                            connection.execute(
                                """DELETE FROM inventory
                                   WHERE guild_id = ? AND user_id = ? AND item_name = ?""",
                                (guild_id, user_id, current_name),
                            )

            updated_price = int(row["price"]) if price is None else price
            updated_description = (
                str(row["description"]) if description is None else description
            )
            current_stock = None if row["stock"] is None else int(row["stock"])
            updated_stock = (
                None
                if unlimited_stock
                else current_stock if stock is None else stock
            )
            current_role_id = None if row["role_id"] is None else int(row["role_id"])
            updated_role_id = (
                None
                if remove_role
                else current_role_id if role_id is None else role_id
            )

            connection.execute(
                """UPDATE shop_items
                   SET item_name = ?, description = ?, price = ?, stock = ?, role_id = ?
                   WHERE guild_id = ? AND item_name = ?""",
                (
                    updated_name,
                    updated_description,
                    updated_price,
                    updated_stock,
                    updated_role_id,
                    guild_id,
                    current_name,
                ),
            )
            return ShopItem(
                name=updated_name,
                description=updated_description,
                price=updated_price,
                stock=updated_stock,
                role_id=updated_role_id,
            )

    def purchase(
        self, guild_id: int, user_id: int, item_name: str, quantity: int
    ) -> tuple[str, int, int, int | None, int | None]:
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            item = connection.execute(
                """SELECT item_name, price, stock, role_id FROM shop_items
                   WHERE guild_id = ? AND item_name = ?"""
                + self._for_update(),
                (guild_id, item_name),
            ).fetchone()
            if item is None:
                raise ShopItemNotFound

            remaining = None if item["stock"] is None else int(item["stock"])
            if remaining is not None and remaining < quantity:
                raise OutOfStock(remaining)

            total = int(item["price"]) * quantity
            self._ensure_account(connection, guild_id, user_id)
            account = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?"
                + self._for_update(),
                (guild_id, user_id),
            ).fetchone()
            balance = int(account["balance"])
            if balance < total:
                raise InsufficientFunds(balance, total)

            connection.execute(
                "UPDATE accounts SET balance = balance - ? WHERE guild_id = ? AND user_id = ?",
                (total, guild_id, user_id),
            )
            if remaining is not None:
                remaining -= quantity
                connection.execute(
                    "UPDATE shop_items SET stock = ? WHERE guild_id = ? AND item_name = ?",
                    (remaining, guild_id, item["item_name"]),
                )
            connection.execute(
                """INSERT INTO inventory
                   (guild_id, user_id, item_name, quantity, cost_basis)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (guild_id, user_id, item_name)
                   DO UPDATE SET quantity = inventory.quantity + excluded.quantity,
                                 cost_basis = inventory.cost_basis + excluded.cost_basis""",
                (guild_id, user_id, item["item_name"], quantity, total),
            )
            role_id = None if item["role_id"] is None else int(item["role_id"])
            return str(item["item_name"]), total, balance - total, remaining, role_id

    def sell(
        self, guild_id: int, user_id: int, item_name: str, quantity: int
    ) -> tuple[str, int, int, int, int, int | None, int | None]:
        """Sell inventory at 80% of its recorded purchase cost."""
        with self._connect(guild_id) as connection:
            connection.execute("BEGIN IMMEDIATE")
            shop_item = connection.execute(
                """SELECT item_name, role_id FROM shop_items
                   WHERE guild_id = ? AND item_name = ?"""
                + self._for_update(),
                (guild_id, item_name),
            ).fetchone()
            item = connection.execute(
                """SELECT item_name, quantity, cost_basis FROM inventory
                   WHERE guild_id = ? AND user_id = ? AND item_name = ?"""
                + self._for_update(),
                (guild_id, user_id, item_name),
            ).fetchone()
            if item is None:
                raise ItemNotInInventory

            owned = int(item["quantity"])
            if owned < quantity:
                raise InsufficientInventory(owned)

            total_cost_basis = int(item["cost_basis"])
            cost_basis_sold = (
                total_cost_basis
                if quantity == owned
                else total_cost_basis * quantity // owned
            )
            refund = cost_basis_sold * 80 // 100
            remaining_quantity = owned - quantity

            self._ensure_account(connection, guild_id, user_id)
            connection.execute(
                """UPDATE accounts SET balance = balance + ?
                   WHERE guild_id = ? AND user_id = ?""",
                (refund, guild_id, user_id),
            )
            balance_row = connection.execute(
                "SELECT balance FROM accounts WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()

            if remaining_quantity:
                connection.execute(
                    """UPDATE inventory
                       SET quantity = ?, cost_basis = cost_basis - ?
                       WHERE guild_id = ? AND user_id = ? AND item_name = ?""",
                    (
                        remaining_quantity,
                        cost_basis_sold,
                        guild_id,
                        user_id,
                        item["item_name"],
                    ),
                )
            else:
                connection.execute(
                    """DELETE FROM inventory
                       WHERE guild_id = ? AND user_id = ? AND item_name = ?""",
                    (guild_id, user_id, item["item_name"]),
                )

            stock_row = connection.execute(
                """SELECT stock FROM shop_items
                   WHERE guild_id = ? AND item_name = ?""",
                (guild_id, item["item_name"]),
            ).fetchone()
            remaining_stock = None
            if stock_row is not None and stock_row["stock"] is not None:
                remaining_stock = int(stock_row["stock"]) + quantity
                connection.execute(
                    """UPDATE shop_items SET stock = ?
                       WHERE guild_id = ? AND item_name = ?""",
                    (remaining_stock, guild_id, item["item_name"]),
                )

            role_id = (
                None
                if shop_item is None or shop_item["role_id"] is None
                else int(shop_item["role_id"])
            )
            return (
                str(item["item_name"]),
                cost_basis_sold,
                refund,
                int(balance_row["balance"]),
                remaining_quantity,
                remaining_stock,
                role_id,
            )

    def inventory(self, guild_id: int, user_id: int) -> list[tuple[str, int]]:
        with self._connect(guild_id) as connection:
            rows = connection.execute(
                """SELECT item_name, quantity FROM inventory
                   WHERE guild_id = ? AND user_id = ?
                   ORDER BY item_name COLLATE NOCASE""",
                (guild_id, user_id),
            ).fetchall()
            return [(str(row["item_name"]), int(row["quantity"])) for row in rows]
