"""SQLite baseline DDL.

Holds the current shape of every table. Changing an existing database is the
business of `_migrations.py`, applied at the end of `create_schema`.
"""

from clear_budget.infrastructure.sqlite._migrations import apply_pending


def create_schema(conn) -> None:
    """Create the baseline schema, then apply any pending migrations."""
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

    # A bill's amount changing from a month onward (the rent increase).
    # One row per change rather than editing the bill in place, because
    # editing in place would rewrite what earlier months reported.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_amount_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            effective_year INTEGER NOT NULL,
            effective_month INTEGER NOT NULL,
            amount_pence INTEGER NOT NULL,
            UNIQUE(bill_id, effective_year, effective_month),
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        )
        """)

    # Evolve an existing database to the current shape. Each step runs once, in
    # order, and any failure that is not "the column is already there" raises.
    apply_pending(cursor)

    conn.commit()
