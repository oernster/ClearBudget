"""SQLite schema DDL and migrations - extracted from database.py for LOC limit."""


def _migrate_credit_cards_schema(cursor) -> None:
    """Add new columns to credit_cards table if they don't exist."""
    columns_to_add = [
        ("interest_rate_apr", "REAL DEFAULT NULL"),
        ("payment_due_day", "INTEGER DEFAULT 1"),
        ("card_expiry_month", "INTEGER DEFAULT NULL"),
        ("card_expiry_year", "INTEGER DEFAULT NULL"),
        ("minimum_payment_pence", "INTEGER DEFAULT NULL"),
        ("active", "INTEGER DEFAULT 1"),
    ]

    for col_name, col_def in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE credit_cards ADD COLUMN {col_name} {col_def}")
        except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
            pass


def create_schema(conn) -> None:
    """Create database schema and run migrations."""
    cursor = conn.cursor()

    # Payment methods table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

    # Ensure bank account exists with id=1
    cursor.execute("""
        INSERT OR IGNORE INTO payment_methods (id, name, type)
        VALUES (1, 'Bank Account', 'bank')
        """)

    # Bill templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount_pence INTEGER NOT NULL,
            payment_method_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            bill_type TEXT NOT NULL,
            day_of_month INTEGER,
            start_year INTEGER NOT NULL,
            start_month INTEGER NOT NULL,
            end_year INTEGER,
            end_month INTEGER,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
        )
        """)

    # Income sources table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount_pence INTEGER NOT NULL,
            is_reliable INTEGER NOT NULL,
            day_of_month INTEGER,
            active INTEGER DEFAULT 1
        )
        """)

    # Months table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS months (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(year, month)
        )
        """)

    # Month bills table (instantiated bills for specific months)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS month_bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_id INTEGER NOT NULL,
            bill_template_id INTEGER,
            name TEXT NOT NULL,
            amount_pence INTEGER NOT NULL,
            payment_method_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            day_of_month INTEGER,
            is_ad_hoc INTEGER DEFAULT 0,
            FOREIGN KEY (month_id) REFERENCES months(id),
            FOREIGN KEY (bill_template_id) REFERENCES bills(id),
            FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
        )
        """)

    # Month income table (instantiated income for specific months)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS month_income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_id INTEGER NOT NULL,
            income_source_id INTEGER,
            name TEXT NOT NULL,
            amount_pence INTEGER NOT NULL,
            is_reliable INTEGER NOT NULL,
            day_of_month INTEGER,
            FOREIGN KEY (month_id) REFERENCES months(id),
            FOREIGN KEY (income_source_id) REFERENCES income_sources(id)
        )
        """)

    # Credit cards table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            credit_limit_pence INTEGER NOT NULL,
            current_balance_used_pence INTEGER NOT NULL DEFAULT 0,
            interest_rate_apr REAL DEFAULT NULL,
            payment_due_day INTEGER DEFAULT 1,
            card_expiry_month INTEGER DEFAULT NULL,
            card_expiry_year INTEGER DEFAULT NULL,
            minimum_payment_pence INTEGER DEFAULT NULL,
            active INTEGER DEFAULT 1
        )
        """)

    # Scheduled (future-dated) credit limit changes, one row per change.
    # No uniqueness: a card may have any number of changes over time.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_limit_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            effective_year INTEGER NOT NULL,
            effective_month INTEGER NOT NULL,
            effective_day INTEGER NOT NULL,
            new_limit_pence INTEGER NOT NULL,
            FOREIGN KEY (card_id) REFERENCES credit_cards(id)
        )
        """)

    # Migrations: add columns to credit_cards if missing (existing databases)
    _migrate_credit_cards_schema(cursor)

    # Settings table (for app configuration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

    # Per-month bill overrides (independent of archive)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_month_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            amount_pence INTEGER NOT NULL,
            payment_method_id INTEGER NOT NULL,
            UNIQUE(bill_id, year, month),
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
        """)

    # Migrate bills added with current-month start_ym to always-visible 2000-01
    cursor.execute(
        "UPDATE bills SET start_year = 2000, start_month = 1" " WHERE start_year > 2000"
    )

    # Add target_card_id to bills (links credit_payment bills to their card)
    try:
        cursor.execute(
            "ALTER TABLE bills ADD COLUMN target_card_id INTEGER DEFAULT NULL"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass

    # Add day_of_month override to bill_month_overrides
    try:
        cursor.execute(
            "ALTER TABLE bill_month_overrides"
            " ADD COLUMN day_of_month INTEGER DEFAULT NULL"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass

    # Add per-card minimum payment percentage
    try:
        cursor.execute(
            "ALTER TABLE credit_cards"
            " ADD COLUMN minimum_payment_percent REAL DEFAULT NULL"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass

    # Track the last month folded into current_balance_used_pence
    try:
        cursor.execute(
            "ALTER TABLE credit_cards"
            " ADD COLUMN balance_applied_year INTEGER DEFAULT NULL"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass
    try:
        cursor.execute(
            "ALTER TABLE credit_cards"
            " ADD COLUMN balance_applied_month INTEGER DEFAULT NULL"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass
    # Day-of-month a balance was manually set as-of (mid-month anchor)
    try:
        cursor.execute(
            "ALTER TABLE credit_cards"
            " ADD COLUMN balance_applied_day INTEGER DEFAULT NULL"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass

    # Per-month bill skips (excludes a bill from one month without deleting it)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_month_skips (
            bill_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            PRIMARY KEY (bill_id, year, month),
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
        """)

    # Per-month one-off (ad-hoc) income, not tied to an income_sources template
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_month_extras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount_pence INTEGER NOT NULL,
            day_of_month INTEGER,
            is_reliable INTEGER NOT NULL
        )
        """)

    # Add "received" flag directly to income_month_extras (independent rows)
    try:
        cursor.execute(
            "ALTER TABLE income_month_extras"
            " ADD COLUMN received INTEGER NOT NULL DEFAULT 0"
        )
    except Exception:  # noqa: S110, BLE001 (idempotent ALTER migration)
        pass

    # Per-month income overrides (mirrors bill_month_overrides)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_month_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            income_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            amount_pence INTEGER NOT NULL,
            day_of_month INTEGER,
            UNIQUE(income_id, year, month),
            FOREIGN KEY (income_id) REFERENCES income_sources(id)
        )
        """)

    # Per-month income skips (mirrors bill_month_skips)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_month_skips (
            income_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            PRIMARY KEY (income_id, year, month),
            FOREIGN KEY (income_id) REFERENCES income_sources(id)
        )
        """)

    # Per-month "bill paid" flags (visual only, doesn't affect totals)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_month_paid (
            bill_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            PRIMARY KEY (bill_id, year, month),
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
        """)

    # Per-month "income received" flags (visual only, doesn't affect totals)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_month_received (
            income_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            PRIMARY KEY (income_id, year, month),
            FOREIGN KEY (income_id) REFERENCES income_sources(id)
        )
        """)

    # Log of amounts automatically applied to the bank balance (by the
    # midnight fold or the same-day prompt). Deleting an item reverses its
    # logged amounts; setting the balance by hand clears the log, since
    # the typed figure supersedes everything applied before it.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS balance_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            amount_pence INTEGER NOT NULL
        )
        """)

    conn.commit()
