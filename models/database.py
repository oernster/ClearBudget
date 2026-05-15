import sqlite3
from datetime import datetime
from pathlib import Path

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_data()

    def _init_schema(self):
        cursor = self.conn.cursor()

        # Payment methods
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_methods (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('bank', 'credit_card')),
                credit_limit REAL,
                current_balance_used REAL,
                is_default INTEGER DEFAULT 0
            )
        ''')

        # Income sources
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS income_sources (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                is_reliable INTEGER DEFAULT 1,
                day_of_month INTEGER,
                active INTEGER DEFAULT 1
            )
        ''')

        # Bill templates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bill_templates (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_method_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                bill_type TEXT NOT NULL CHECK(bill_type IN ('fixed', 'variable', 'expiring')),
                day_of_month INTEGER,
                start_ym TEXT,
                end_ym TEXT,
                active INTEGER DEFAULT 1,
                FOREIGN KEY(payment_method_id) REFERENCES payment_methods(id)
            )
        ''')

        # Months
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS months (
                id INTEGER PRIMARY KEY,
                year_month TEXT UNIQUE NOT NULL,
                is_archived INTEGER DEFAULT 0,
                notes TEXT
            )
        ''')

        # Month bills
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS month_bills (
                id INTEGER PRIMARY KEY,
                month_id INTEGER NOT NULL,
                bill_template_id INTEGER,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_method_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                day_of_month INTEGER,
                is_ad_hoc INTEGER DEFAULT 0,
                FOREIGN KEY(month_id) REFERENCES months(id),
                FOREIGN KEY(bill_template_id) REFERENCES bill_templates(id),
                FOREIGN KEY(payment_method_id) REFERENCES payment_methods(id)
            )
        ''')

        # Month income
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS month_income (
                id INTEGER PRIMARY KEY,
                month_id INTEGER NOT NULL,
                income_source_id INTEGER,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                is_reliable INTEGER DEFAULT 1,
                day_of_month INTEGER,
                FOREIGN KEY(month_id) REFERENCES months(id),
                FOREIGN KEY(income_source_id) REFERENCES income_sources(id)
            )
        ''')

        self.conn.commit()

    def _seed_data(self):
        """Seed initial data if empty."""
        cursor = self.conn.cursor()

        # Check if already seeded
        cursor.execute('SELECT COUNT(*) as count FROM payment_methods')
        if cursor.fetchone()['count'] > 0:
            return

        # Payment methods
        payment_methods = [
            ('Bank Account', 'bank', None, 0, 1),
            ('CapitalOne', 'credit_card', 1750, 1415.36, 0),
            ('Jaja', 'credit_card', 3000, 2954.44, 0),
            ('Vanquis', 'credit_card', 1200, 1126.98, 0),
        ]
        for name, ptype, limit, balance, is_default in payment_methods:
            cursor.execute('''
                INSERT INTO payment_methods (name, type, credit_limit, current_balance_used, is_default)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, ptype, limit, balance, is_default))

        # Income sources
        income_sources = [
            ('Universal Credit', 1200, 1, 21, 1),
            ('M+D Loan', 600, 1, 1, 1),
        ]
        for name, amount, reliable, day, active in income_sources:
            cursor.execute('''
                INSERT INTO income_sources (name, amount, is_reliable, day_of_month, active)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, amount, reliable, day, active))

        # Get payment method IDs
        cursor.execute('SELECT id FROM payment_methods WHERE name = ?', ('Bank Account',))
        bank_id = cursor.fetchone()['id']
        cursor.execute('SELECT id FROM payment_methods WHERE name = ?', ('CapitalOne',))
        capone_id = cursor.fetchone()['id']

        # Bill templates (bank account)
        bills_bank = [
            ('Rent', 1350, bank_id, 'housing', 'fixed', 1, '2026-01', None),
            ('Electricity', 95, bank_id, 'utilities', 'fixed', 15, '2026-01', None),
            ('C Tax', 135, bank_id, 'utilities', 'fixed', 10, '2026-01', None),
            ('Car Insurance', 42, bank_id, 'utilities', 'fixed', 15, '2026-01', None),
            ('Milk', 16, bank_id, 'utilities', 'fixed', 1, '2026-01', None),
            ('Internet', 41, bank_id, 'utilities', 'fixed', 10, '2026-01', None),
            ('Three Mobile', 22, bank_id, 'utilities', 'fixed', 1, '2026-01', None),
            ('AA', 14, bank_id, 'utilities', 'fixed', 1, '2026-01', None),
            ('Gas', 15, bank_id, 'utilities', 'fixed', 1, '2026-01', None),
            ('Water', 40, bank_id, 'utilities', 'fixed', 10, '2026-01', None),
            ('BUPA', 26, bank_id, 'utilities', 'fixed', 1, '2026-01', None),
            ('Claude', 18, bank_id, 'subscriptions', 'fixed', 1, '2026-01', None),
            ('Camera Amazon Layaway', 60, bank_id, 'one_time', 'expiring', 1, '2026-01', '2026-11'),
            ('Sofa Repayment', 42, bank_id, 'one_time', 'expiring', 1, '2026-01', '2027-09'),
            ('Jaja Payment', 150, bank_id, 'credit_payment', 'fixed', 1, '2026-01', None),
            ('CapitalOne Payment', 80, bank_id, 'credit_payment', 'fixed', 1, '2026-01', None),
            ('Vanquis Payment', 70, bank_id, 'credit_payment', 'fixed', 1, '2026-01', None),
            ('Groceries/Discretionary', 162, bank_id, 'groceries', 'variable', None, '2026-01', None),
        ]

        for name, amount, pm_id, category, btype, day, start, end in bills_bank:
            cursor.execute('''
                INSERT INTO bill_templates (name, amount, payment_method_id, category, bill_type, day_of_month, start_ym, end_ym, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (name, amount, pm_id, category, btype, day, start, end))

        # Bills on CapitalOne card
        bills_capone = [
            ('Render', 58, capone_id, 'subscriptions', 'fixed', 1, '2026-01', None),
            ('PrimeVideo', 3, capone_id, 'subscriptions', 'fixed', 1, '2026-01', None),
            ('Backblaze', 9, capone_id, 'subscriptions', 'fixed', 1, '2026-01', None),
            ('GitHub', 8, capone_id, 'subscriptions', 'fixed', 1, '2026-01', None),
            ('Prime', 9, capone_id, 'subscriptions', 'fixed', 1, '2026-01', None),
        ]

        for name, amount, pm_id, category, btype, day, start, end in bills_capone:
            cursor.execute('''
                INSERT INTO bill_templates (name, amount, payment_method_id, category, bill_type, day_of_month, start_ym, end_ym, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (name, amount, pm_id, category, btype, day, start, end))

        self.conn.commit()

    def execute(self, query, params=None):
        """Execute a query and return cursor."""
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
