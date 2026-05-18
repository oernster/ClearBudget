"""Working day calculator — adjust dates for weekends and UK holidays."""

from datetime import date, timedelta


class WorkingDayCalculatorService:
    """Calculate working day adjustments for payment due dates."""

    # UK bank holidays (month, day) — fixed holidays and approximate dates for moveable ones
    # Moveable holidays (Easter, bank holidays) are approximated for 2026-2030
    UK_HOLIDAYS = [
        (1, 1),    # New Year's Day
        (4, 13),   # Easter Monday 2026
        (5, 4),    # Early May bank holiday
        (5, 25),   # Spring bank holiday
        (8, 31),   # Summer bank holiday
        (12, 25),  # Christmas Day
        (12, 26),  # Boxing Day
    ]

    @staticmethod
    def adjust_to_working_day(
        day_of_month: int, year: int, month: int
    ) -> int:
        """
        Adjust a day of month to the preceding working day if it's a weekend/holiday.

        Args:
            day_of_month: Day of month (1-31)
            year: Year
            month: Month (1-12)

        Returns:
            Adjusted day of month (may be in previous month if needed).
            Tuple (adjusted_day, adjusted_month, adjusted_year) for safe handling.
        """
        try:
            target_date = date(year, month, day_of_month)
        except ValueError:
            # Invalid day for month (e.g., Feb 30) — return last day of month
            if month == 2:
                target_date = date(year, 3, 1) - timedelta(days=1)
            else:
                target_date = date(year, month + 1, 1) - timedelta(days=1)

        # Walk back from target_date until we find a working day (Mon-Fri, not holiday)
        current = target_date
        max_iterations = 10  # Safety limit
        iteration = 0

        while iteration < max_iterations:
            # 0=Monday, 6=Sunday
            weekday = current.weekday()
            is_weekend = weekday >= 5  # Saturday or Sunday
            is_holiday = (current.month, current.day) in WorkingDayCalculatorService.UK_HOLIDAYS

            if not is_weekend and not is_holiday:
                break

            current -= timedelta(days=1)
            iteration += 1

        return current.day

    @staticmethod
    def format_due_date_display(
        nominal_day: int, adjusted_day: int, month: int, year: int
    ) -> str:
        """Format a due date for display, noting adjustment if any."""
        if nominal_day == adjusted_day:
            return f"{adjusted_day}"
        return f"{adjusted_day} (nominal {nominal_day})"
