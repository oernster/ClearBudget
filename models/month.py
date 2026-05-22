from datetime import datetime


class Month:
    @staticmethod
    def get_or_create(db, year_month):
        """Get existing month or create from templates."""
        cursor = db.execute("SELECT id FROM months WHERE year_month = ?", (year_month,))
        result = cursor.fetchone()
        if result:
            return result["id"]

        # Create new month
        cursor = db.execute(
            'INSERT INTO months (year_month, is_archived, notes) VALUES (?, 0, "")',
            (year_month,),
        )
        db.commit()
        month_id = cursor.lastrowid

        # Populate from bill templates
        start_year, start_month = map(int, year_month.split("-"))
        cursor = db.execute(
            """
            SELECT id, name, amount, payment_method_id, category, bill_type, day_of_month, start_ym, end_ym
            FROM bill_templates
            WHERE active = 1
            AND start_ym <= ?
            AND (end_ym IS NULL OR end_ym >= ?)
        """,
            (year_month, year_month),
        )

        for row in cursor.fetchall():
            db.execute(
                """
                INSERT INTO month_bills (month_id, bill_template_id, name, amount, payment_method_id, category, day_of_month, is_ad_hoc)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
                (
                    month_id,
                    row["id"],
                    row["name"],
                    row["amount"],
                    row["payment_method_id"],
                    row["category"],
                    row["day_of_month"],
                ),
            )

        # Populate income
        cursor = db.execute("""
            SELECT id, name, amount, is_reliable, day_of_month
            FROM income_sources
            WHERE active = 1
        """)

        for row in cursor.fetchall():
            db.execute(
                """
                INSERT INTO month_income (month_id, income_source_id, name, amount, is_reliable, day_of_month)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    month_id,
                    row["id"],
                    row["name"],
                    row["amount"],
                    row["is_reliable"],
                    row["day_of_month"],
                ),
            )

        db.commit()
        return month_id

    @staticmethod
    def get_month_data(db, year_month):
        """Fetch complete month data."""
        month_id = Month.get_or_create(db, year_month)

        cursor = db.execute("SELECT * FROM months WHERE id = ?", (month_id,))
        month = cursor.fetchone()

        cursor = db.execute(
            "SELECT * FROM month_bills WHERE month_id = ? ORDER BY day_of_month, name",
            (month_id,),
        )
        bills = cursor.fetchall()

        cursor = db.execute(
            "SELECT * FROM month_income WHERE month_id = ? ORDER BY day_of_month",
            (month_id,),
        )
        income = cursor.fetchall()

        return {
            "id": month_id,
            "year_month": month["year_month"],
            "is_archived": month["is_archived"],
            "bills": [dict(b) for b in bills],
            "income": [dict(i) for i in income],
        }

    @staticmethod
    def archive(db, year_month):
        """Mark month as archived."""
        db.execute(
            "UPDATE months SET is_archived = 1 WHERE year_month = ?", (year_month,)
        )
        db.commit()

    @staticmethod
    def unarchive(db, year_month):
        """Mark month as active."""
        db.execute(
            "UPDATE months SET is_archived = 0 WHERE year_month = ?", (year_month,)
        )
        db.commit()

    @staticmethod
    def list_months(db, archived=False):
        """List all months."""
        cursor = db.execute(
            "SELECT year_month FROM months WHERE is_archived = ? ORDER BY year_month DESC",
            (1 if archived else 0,),
        )
        return [row["year_month"] for row in cursor.fetchall()]
