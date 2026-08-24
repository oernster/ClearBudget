"""Builder mixin for MonthView - UI construction extracted to stay under LOC limit."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
)

from clear_budget.ui import label_roles
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    build_centered_nav_header,
    fmt,
    nav_glyph_height,
)
from clear_budget.ui.utils.tab_icons import build_tab_buttons
from clear_budget.ui.widgets._tray_buttons import (
    build_budgets_button,
    build_info_button,
    build_save_load_buttons,
    build_settings_bank_buttons,
    build_users_button,
)
from clear_budget.ui.utils.table_focus import keyboard_only_focus
from clear_budget.ui.utils.text_metrics import apply_comfortable_rows

INCOME_VISIBLE_ROWS = 5


class MonthViewBuilderMixin:
    """Methods for building the MonthView widget sections."""

    def _build_header_section(self, layout: QVBoxLayout) -> tuple:
        header_layout = QVBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        next_btn = self.next_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(_glyph_h)
        self.budgets_btn = build_budgets_button(_glyph_h)
        self.users_btn = build_users_button(_glyph_h)
        _sep, self.settings_btn, self.bank_btn = build_settings_bank_buttons(_glyph_h)
        self.info_btn = build_info_button(_glyph_h)
        # The four primary tabs live in this tray, so every view builds its
        # own set; MainWindow wires them and keeps the current-tab mark in
        # step across all four.
        self.tab_btns = build_tab_buttons(_glyph_h)
        _ym = self.view_model.current_month
        (
            self.nav_header,
            self.month_label,
            self.theme_btn,
        ) = build_centered_nav_header(
            f"{MONTH_NAMES[_ym.month]} {_ym.year}",
            prev_btn=self.prev_btn,
            next_btn=next_btn,
            leading=(
                self.load_btn,
                self.save_btn,
                self.budgets_btn,
                self.users_btn,
                self.settings_btn,
                self.bank_btn,
                _sep,
            ),
            tabs=self.tab_btns[:-1],
            pre_theme=(self.tab_btns[-1],),
            trailing=(self.info_btn,),
        )

        # No line pointing at "the Solvency tab" any more. The tabs are
        # pictures in the tray, so a sentence naming one by a word that is
        # nowhere on screen sends the reader looking for something that does
        # not exist. The shield icon carries its own tooltip; nothing is left
        # for this to say.
        self.overdraft_warning_label = QLabel("")
        self.overdraft_warning_label.setObjectName(label_roles.WARN_NOTE)
        self.overdraft_warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overdraft_warning_label.setWordWrap(True)
        self.overdraft_warning_label.setVisible(False)
        header_layout.addWidget(self.overdraft_warning_label)

        summary_layout = QHBoxLayout()
        self.income_label = QLabel(f"Income: {fmt(0)}")
        self.income_label.setObjectName(label_roles.VALUE)
        self.bills_label = QLabel(f"Bills: {fmt(0)}")
        self.bills_label.setObjectName(label_roles.VALUE)
        self.edit_balance_btn = QPushButton("📝")
        self.edit_balance_btn.setObjectName(label_roles.ICON_ACTION)
        self.edit_balance_btn.setMaximumWidth(32)
        self.edit_balance_btn.setMaximumHeight(26)
        self.edit_balance_btn.setToolTip("Edit bank balance")
        self.balance_label = QLabel(f"Balance: {fmt(0)}")
        self.balance_label.setObjectName(label_roles.GOOD)
        summary_layout.addWidget(self.income_label)
        summary_layout.addWidget(self.bills_label)
        summary_layout.addStretch()
        summary_layout.addWidget(self.edit_balance_btn)
        summary_layout.addWidget(self.balance_label)
        header_layout.addLayout(summary_layout)
        layout.addLayout(header_layout)
        return self.prev_btn, next_btn

    def _build_bills_section(self, layout: QVBoxLayout) -> None:
        bills_group = QGroupBox("Bills")
        bills_layout = QVBoxLayout()
        self.bills_table = QTableWidget()
        apply_comfortable_rows(self.bills_table)
        keyboard_only_focus(self.bills_table)
        self.bills_table.setColumnCount(8)
        self.bills_table.setHorizontalHeaderLabels(
            [
                "Name",
                "Amount",
                "Category",
                "Payment Method",
                "Due",
                "Active",
                "Skip",
                "Paid",
            ]
        )
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        # Indicator and row-header colours come from the app stylesheet, so
        # they follow the theme (see _theme_controls.label_roles_qss).
        _bh = self.bills_table.horizontalHeader()
        _bh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _bh.setStretchLastSection(False)
        self.bills_table.verticalHeader().sectionClicked.connect(
            self._on_bill_row_header_click
        )
        self.bills_table.horizontalHeader().sectionClicked.connect(
            self.on_bills_header_click
        )
        bills_layout.addWidget(self.bills_table)
        bills_btn_layout = QHBoxLayout()
        self.add_bill_btn = QPushButton("Add Bill")
        self.delete_bill_btn = QPushButton("Delete Bill")
        bills_btn_layout.addWidget(self.add_bill_btn)
        bills_btn_layout.addStretch()
        bills_btn_layout.addWidget(self.delete_bill_btn)
        bills_layout.addLayout(bills_btn_layout)
        bills_group.setLayout(bills_layout)
        bills_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(bills_group, 1)

    def _build_income_section(self, layout: QVBoxLayout) -> None:
        income_group = QGroupBox("Income")
        income_layout = QVBoxLayout()
        self.income_table = QTableWidget()
        apply_comfortable_rows(self.income_table)
        keyboard_only_focus(self.income_table)
        self.income_table.setColumnCount(7)
        self.income_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Reliable", "Due Day", "Active", "Skip", "Received"]
        )
        self.income_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.income_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.income_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        _ih = self.income_table.horizontalHeader()
        _ih.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _ih.setStretchLastSection(False)
        self.income_table.verticalHeader().sectionClicked.connect(
            self._on_income_row_header_click
        )
        self.income_table.horizontalHeader().sectionClicked.connect(
            self.on_income_header_click
        )
        income_layout.addWidget(self.income_table)
        income_btn_layout = QHBoxLayout()
        self.add_income_btn = QPushButton("Add Income")
        self.delete_income_btn = QPushButton("Delete Income")
        income_btn_layout.addWidget(self.add_income_btn)
        income_btn_layout.addStretch()
        income_btn_layout.addWidget(self.delete_income_btn)
        income_layout.addLayout(income_btn_layout)
        income_group.setLayout(income_layout)

        _row_height = self.income_table.verticalHeader().defaultSectionSize()
        _header_height = self.income_table.horizontalHeader().sizeHint().height()
        _frame = self.income_table.frameWidth() * 2
        self.income_table.setMaximumHeight(
            _header_height + _row_height * INCOME_VISIBLE_ROWS + _frame
        )
        income_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        layout.addWidget(income_group, 0)

    def _connect_button_signals(
        self, prev_btn: QPushButton, next_btn: QPushButton
    ) -> None:
        prev_btn.clicked.connect(self.view_model.previous_month)
        next_btn.clicked.connect(self.view_model.next_month)
        self.edit_balance_btn.clicked.connect(self.on_edit_balance)
        self.add_bill_btn.clicked.connect(self.on_add_bill)
        self.delete_bill_btn.clicked.connect(self.on_delete_bill)
        self.add_income_btn.clicked.connect(self.on_add_income)
        self.delete_income_btn.clicked.connect(self.on_delete_income)
