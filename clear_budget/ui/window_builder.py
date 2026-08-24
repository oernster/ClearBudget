"""Assembling one open budget into a window, with progress as it goes.

Everything between a database connection and a window the user can look at:
the repositories over that connection, the services above them, the catch-up
those services do for the days since the last run, the view models and the
window itself.

Split out of `main.py`, which reached the band the size cap treats as one edit
from failing (tests/structural/test_loc_limits.py). The slice is cohesive
rather than arbitrary: this is the wiring for ONE budget, whereas the
composition root keeps what only it can hold, the session, the windows, the
database connection and the order in which one replaces another.

The stage count lives here for the same reason it lived in the composition
root before: this is now the only place that knows both halves of the build,
the services counted here and the tabs counted by the window, so the window is
handed the offset it starts at rather than counting for itself.
"""

from __future__ import annotations

import sys

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.application.services.update_service import (
    UpdateService,
    platform_key_for,
)
from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.infrastructure.update.github_release_source import (
    GitHubReleaseSource,
)
from clear_budget.ui.main_window import MainWindow
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.version import __version__

# Stages the sign-in screen's bar is divided into: the services, then one per
# tab, then the window's chrome.
SERVICE_STAGES = 2
TAB_STAGES = 5
BUILD_STAGES = SERVICE_STAGES + TAB_STAGES + 1


def build_main_window(
    database: Database,
    current_user: User,
    user_store: UserStore,
    progress=None,
) -> MainWindow:
    """Wire all services and return a ready MainWindow.

    `progress(done, total, label)` is called as each stage completes, so the
    sign-in screen can show how far along the build is. None builds silently,
    which is what a rebuild behind an already-visible window wants.
    """
    report = progress or (lambda *_args, **_kw: None)
    report(0, BUILD_STAGES, "reading your budget")
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
    budget_service.update_card_balances_for_elapsed_dates()
    budget_service.apply_elapsed_limit_changes()
    budget_service.apply_elapsed_bank_transactions()
    budget_service.auto_archive_elapsed_months(current_month=YearMonth.today())
    report(1, BUILD_STAGES, "catching up on elapsed days")
    month_view_model = MonthViewModel(budget_service=budget_service)
    solvency_view_model = SolvencyViewModel(budget_service=budget_service)
    update_service = UpdateService(
        source=GitHubReleaseSource(),
        current_version=__version__,
        platform_key=platform_key_for(sys.platform),
    )
    return MainWindow(
        month_view_model=month_view_model,
        solvency_view_model=solvency_view_model,
        current_user=current_user,
        user_store=user_store,
        db_path=database.db_path,
        update_service=update_service,
        progress=report,
        first_stage=SERVICE_STAGES,
        total_stages=BUILD_STAGES,
    )
