"""Archive helper functions extracted from BudgetService to keep file under 400 LOC."""

from clear_budget.domain.value_objects.year_month import YearMonth


def _get_recorded_months(conn) -> list[YearMonth]:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT m.year, m.month
        FROM months m
        WHERE m.id IN (
            SELECT DISTINCT month_id FROM month_bills
            UNION
            SELECT DISTINCT month_id FROM month_income
        )
        ORDER BY m.year ASC, m.month ASC
    """)
    rows = cursor.fetchall()
    return [YearMonth(row['year'], row['month']) for row in rows]


def _do_archive_month(conn, year_month: YearMonth, month_generator) -> None:  # pragma: no cover
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM months WHERE year = ? AND month = ?",
        (year_month.year, year_month.month),
    )
    existing = cursor.fetchone()

    if existing:
        month_id = existing['id']
        cursor.execute("DELETE FROM month_bills WHERE month_id = ?", (month_id,))
        cursor.execute("DELETE FROM month_income WHERE month_id = ?", (month_id,))
    else:
        cursor.execute(
            "INSERT INTO months (year, month) VALUES (?, ?)",
            (year_month.year, year_month.month),
        )
        month_id = cursor.lastrowid

    month_bills = month_generator.generate_month_bills(year_month=year_month, month_id=month_id)
    month_income = month_generator.generate_month_income(year_month=year_month, month_id=month_id)

    for bill in month_bills:
        cursor.execute(
            """
            INSERT INTO month_bills
            (month_id, bill_template_id, name, amount_pence, payment_method_id, category, day_of_month, is_ad_hoc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bill.month_id,
                bill.bill_template_id,
                bill.name,
                bill.amount.pence,
                bill.payment_method_id,
                bill.category,
                bill.day_of_month,
                1 if bill.is_ad_hoc else 0,
            ),
        )

    for inc in month_income:
        cursor.execute(
            """
            INSERT INTO month_income
            (month_id, income_source_id, name, amount_pence, is_reliable, day_of_month)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                inc.month_id,
                inc.income_source_id,
                inc.name,
                inc.amount.pence,
                1 if inc.is_reliable else 0,
                inc.day_of_month,
            ),
        )

    conn.commit()
