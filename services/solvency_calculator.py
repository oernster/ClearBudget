from datetime import datetime
from models.month import Month


class SolvencyCalculator:
    @staticmethod
    def calculate_current_month(db, year_month):
        """Calculate balance and solvency for current month."""
        month_data = Month.get_month_data(db, year_month)

        total_income = sum(i["amount"] for i in month_data["income"])
        total_bills = sum(b["amount"] for b in month_data["bills"])
        balance = total_income - total_bills

        deficit = max(0, -balance)

        return {
            "year_month": year_month,
            "total_income": total_income,
            "total_bills": total_bills,
            "balance": balance,
            "deficit": deficit,
            "bills": month_data["bills"],
            "income": month_data["income"],
        }

    @staticmethod
    def calculate_desired_acquire(db, year_month):
        """
        Calculate how much to acquire:
        deficit + £600 buffer + next 2 months shortfall (using reliable income only)
        """
        current = SolvencyCalculator.calculate_current_month(db, year_month)
        deficit = current["deficit"]

        # Get next 2 months
        year, month = map(int, year_month.split("-"))
        next_months = []
        for i in range(1, 3):
            next_month = month + i
            next_year = year
            if next_month > 12:
                next_month -= 12
                next_year += 1
            next_ym = f"{next_year:04d}-{next_month:02d}"
            next_months.append(next_ym)

        forward_shortfall = 0
        for ym in next_months:
            m = SolvencyCalculator.calculate_current_month(db, ym)
            reliable_income = sum(i["amount"] for i in m["income"] if i["is_reliable"])
            total_bills = m["total_bills"]
            net = reliable_income - total_bills
            if net < 0:
                forward_shortfall += abs(net)

        desired = deficit + 600 + forward_shortfall

        return {
            "deficit": deficit,
            "buffer": 600,
            "forward_shortfall": forward_shortfall,
            "desired_acquire": desired,
            "next_months": next_months,
        }

    @staticmethod
    def check_card_exhaustion(db, year_month):
        """
        Check credit cards for exhaustion risk.
        Return warnings for cards that will max out within 3 months.
        """
        month_data = Month.get_month_data(db, year_month)

        # Group bills by payment method
        bills_by_method = {}
        for bill in month_data["bills"]:
            pm_id = bill["payment_method_id"]
            if pm_id not in bills_by_method:
                bills_by_method[pm_id] = []
            bills_by_method[pm_id].append(bill)

        # Get payment methods
        cursor = db.execute(
            'SELECT id, name, type, credit_limit, current_balance_used FROM payment_methods WHERE type = "credit_card"'
        )
        cards = cursor.fetchall()

        warnings = []
        for card in cards:
            card_id = card["id"]
            bills_on_card = bills_by_method.get(card_id, [])
            monthly_charge = sum(b["amount"] for b in bills_on_card)

            # Get payment to this card
            payment_cursor = db.execute(
                'SELECT amount FROM month_bills WHERE category = "credit_payment" AND payment_method_id = ? AND month_id = ?',
                (1, 1),  # Simplified - would need actual month_id
            )

            # For now, hardcode known payments
            monthly_payments = {
                2: 80,  # CapitalOne
                3: 150,  # Jaja
                4: 70,  # Vanquis
            }

            payment_out = monthly_payments.get(card_id, 0)
            net_monthly = monthly_charge - payment_out

            available = card["credit_limit"] - card["current_balance_used"]

            if net_monthly > 0 and available > 0:
                months_until_max = available / net_monthly
            else:
                months_until_max = float("inf")

            if months_until_max <= 3:
                warnings.append(
                    {
                        "card": card["name"],
                        "available": available,
                        "monthly_charge": monthly_charge,
                        "monthly_payment": payment_out,
                        "net_monthly": net_monthly,
                        "months_until_max": months_until_max,
                        "status": "danger" if months_until_max <= 1 else "warning",
                    }
                )

        return warnings

    @staticmethod
    def check_bank_cashflow(db, year_month):
        """
        Check daily cashflow on bank account to ensure no negative balance.
        Returns timeline of when account might go negative.
        """
        month_data = Month.get_month_data(db, year_month)

        # Get bank account ID
        cursor = db.execute(
            'SELECT id FROM payment_methods WHERE name = "Bank Account"'
        )
        bank_id = cursor.fetchone()["id"]

        # Filter to bank account only
        bank_bills = [
            b for b in month_data["bills"] if b["payment_method_id"] == bank_id
        ]
        bank_income = month_data["income"]

        # Create daily timeline
        events = []
        for bill in bank_bills:
            if bill["day_of_month"]:
                events.append(
                    ("out", bill["day_of_month"], bill["amount"], bill["name"])
                )

        for inc in bank_income:
            if inc["day_of_month"]:
                events.append(("in", inc["day_of_month"], inc["amount"], inc["name"]))

        # Sort by day
        events.sort(key=lambda x: x[1])

        # Simulate cashflow
        balance = 0  # Start of month balance unknown, assume 0 for warning purposes
        warnings = []

        for event_type, day, amount, name in events:
            if event_type == "out":
                balance -= amount
            else:
                balance += amount

            if balance < 0:
                warnings.append(
                    {
                        "day": day,
                        "amount": amount,
                        "name": name,
                        "shortfall": abs(balance),
                        "event": event_type,
                    }
                )

        return warnings
