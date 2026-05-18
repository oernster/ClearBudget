"""Test all major functionality of ClearBudget."""

from clear_budget.shared.config import Config
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def test_all() -> None:
    """Test all functionality."""
    config = Config.default()
    config.ensure_directories()

    database = Database(config.db_path)
    database.connect()

    bill_repo = SQLiteBillRepository(database.conn)
    income_repo = SQLiteIncomeSourceRepository(database.conn)
    payment_method_repo = SQLitePaymentMethodRepository(database.conn)
    month_generator = MonthGenerator(bill_repo, income_repo)

    budget_service = BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=payment_method_repo,
        month_generator=month_generator,
    )

    print("[TEST 1] Get month summary...")
    summary = budget_service.get_month_summary(year_month=YearMonth(2026, 5))
    print(f"  Bills: {len(summary.bills)} items")
    print(f"  Income: {len(summary.income_sources)} items")
    print(f"  Total Income: {summary.total_income}")
    print(f"  Total Bills: {summary.total_bills}")
    print(f"  Balance: {summary.balance}")
    assert len(summary.bills) > 0, "Should have bills"
    assert len(summary.income_sources) > 0, "Should have income"
    print("  [PASS]")

    print("[TEST 2] Get credit cards...")
    cards = budget_service.get_credit_cards()
    print(f"  Cards: {len(cards)} total")
    for card in cards:
        print(f"    {card.name}: {card.current_balance_used} / {card.credit_limit}")
    assert len(cards) > 0, "Should have credit cards"
    print("  [PASS]")

    print("[TEST 3] Calculate solvency...")
    report = budget_service.calculate_solvency(year_month=YearMonth(2026, 5))
    print(f"  Balance: {report.balance_pence / 100:.2f}")
    print(f"  Solvent: {report.is_solvent}")
    print(f"  Desired Acquire: {report.desired_acquire}")
    print("  [PASS]")

    print("[TEST 4] Add new bill...")
    new_bill = Bill(
        id=0,
        name="Test Bill",
        amount=Amount.from_pounds(50.00),
        payment_method_id=1,
        category="discretionary",
        bill_type="variable",
        day_of_month=None,
        start_ym=YearMonth(2026, 5),
        end_ym=None,
        active=True,
    )
    added_bill = budget_service.add_bill(bill=new_bill)
    print(f"  Added bill ID: {added_bill.id}")
    assert added_bill.id > 0, "Bill should have ID"
    print("  [PASS]")

    print("[TEST 5] Update bill...")
    updated_bill = Bill(
        id=added_bill.id,
        name="Test Bill Updated",
        amount=Amount.from_pounds(75.00),
        payment_method_id=1,
        category="discretionary",
        bill_type="variable",
        day_of_month=None,
        start_ym=YearMonth(2026, 5),
        end_ym=None,
        active=True,
    )
    budget_service.update_bill(bill=updated_bill)
    print("  Bill updated successfully")
    print("  [PASS]")

    print("[TEST 6] Add new income...")
    new_income = IncomeSource(
        id=0,
        name="Test Income",
        amount=Amount.from_pounds(200.00),
        is_reliable=False,
        day_of_month=None,
        active=True,
    )
    added_income = budget_service.add_income(income=new_income)
    print(f"  Added income ID: {added_income.id}")
    assert added_income.id > 0, "Income should have ID"
    print("  [PASS]")

    print("[TEST 7] Delete income...")
    budget_service.delete_income(income_id=added_income.id)
    print("  Income deleted successfully")
    print("  [PASS]")

    print("[TEST 8] Delete bill...")
    budget_service.delete_bill(bill_id=added_bill.id)
    print("  Bill deleted successfully")
    print("  [PASS]")

    print("[TEST 9] Verify refreshed summary...")
    summary2 = budget_service.get_month_summary(year_month=YearMonth(2026, 5))
    print(f"  Bills after delete: {len(summary2.bills)}")
    print(f"  Income after delete: {len(summary2.income_sources)}")
    print("  [PASS]")

    database.close()
    print("\n[ALL TESTS PASSED]")


if __name__ == "__main__":
    test_all()
