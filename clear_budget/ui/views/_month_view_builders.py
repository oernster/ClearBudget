"""Builder mixin for MonthView - UI construction extracted to stay under LOC limit."""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QGroupBox,
    QLabel,
    QHeaderView,
    QWidget,
)
from PySide6.QtCore import Qt

from clear_budget.ui.utils.format_helpers import MONTH_NAMES, build_nav_month_widget, fmt
from clear_budget.ui import ui_scale


class MonthViewBuilderMixin:
    """Methods for building the MonthView widget sections."""

    def _build_header_section(self, layout: QVBoxLayout) -> tuple:
        header_layout = QVBoxLayout()
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        next_btn = QPushButton("Next →")
        next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.archive_btn = QPushButton("Archive Month")
        _ym = self.view_model.current_month
        _nav_center, self.month_label = build_nav_month_widget(
            f"{MONTH_NAMES[_ym.month]} {_ym.year}"
        )
        left_group = QWidget()
        left_lo = QHBoxLayout(left_group)
        left_lo.setContentsMargins(0, 0, 0, 0)
        left_lo.addWidget(self.prev_btn)
        left_lo.addStretch()
        right_group = QWidget()
        right_lo = QHBoxLayout(right_group)
        right_lo.setContentsMargins(0, 0, 0, 0)
        right_lo.addStretch()
        right_lo.addWidget(self.archive_btn)
        right_lo.addWidget(next_btn)
        nav_layout.addWidget(left_group, 1)
        nav_layout.addWidget(_nav_center, 0)
        nav_layout.addWidget(right_group, 1)
        header_layout.addLayout(nav_layout)

        summary_layout = QHBoxLayout()
        self.income_label = QLabel(f"Income: {fmt(0)}")
        self.income_label.setStyleSheet(
            ui_scale.style("font-size: 20px; padding: 5px;")
        )
        self.bills_label = QLabel(f"Bills: {fmt(0)}")
        self.bills_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px;"))
        self.edit_balance_btn = QPushButton("📝")
        self.edit_balance_btn.setMaximumWidth(28)
        self.edit_balance_btn.setMaximumHeight(22)
        self.edit_balance_btn.setStyleSheet(
            ui_scale.style(
                "QPushButton { border: none; background-color: transparent;"
                " color: #34d399; font-size: 20px; padding: 0px; }"
                "QPushButton:hover { background-color: #1a1a2e; border-radius: 3px; }"
            )
        )
        self.balance_label = QLabel(f"Balance: {fmt(0)}")
        self.balance_label.setStyleSheet(
            ui_scale.style(
                "font-size: 20px; font-weight: bold; color: #34d399; padding: 5px;"
            )
        )
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
        self.bills_table.setColumnCount(7)
        self.bills_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Category", "Payment Method", "Due", "Active", "Skip"]
        )
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.bills_table.setStyleSheet(
            "QTableWidget::indicator{width:15px;height:15px;border:2px solid #9ca3af;"
            "border-radius:3px;background:transparent;}"
            "QTableWidget::indicator:checked{background:#34d399;border-color:#34d399;}"
            "QTableWidget::indicator:unchecked:hover{border-color:#d1d5db;}"
        )
        _bh = self.bills_table.horizontalHeader()
        _bh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _bh.setStretchLastSection(False)
        self.bills_table.verticalHeader().setStyleSheet(
            "QHeaderView::section { color: #34d399; }"
        )
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
        self.delete_bill_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bills_btn_layout.addWidget(self.add_bill_btn)
        bills_btn_layout.addStretch()
        bills_btn_layout.addWidget(self.delete_bill_btn)
        bills_layout.addLayout(bills_btn_layout)
        bills_group.setLayout(bills_layout)
        layout.addWidget(bills_group)

    def _build_income_section(self, layout: QVBoxLayout) -> None:
        income_group = QGroupBox("Income")
        income_layout = QVBoxLayout()
        self.income_table = QTableWidget()
        self.income_table.setColumnCount(5)
        self.income_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Reliable", "Due Day", "Active"]
        )
        self.income_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.income_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.income_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        _ih = self.income_table.horizontalHeader()
        _ih.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _ih.setStretchLastSection(False)
        self.income_table.setStyleSheet(
            "QTableWidget::indicator{width:15px;height:15px;border:2px solid #9ca3af;"
            "border-radius:3px;background:transparent;}"
            "QTableWidget::indicator:checked{background:#34d399;border-color:#34d399;}"
            "QTableWidget::indicator:unchecked:hover{border-color:#d1d5db;}"
        )
        self.income_table.verticalHeader().setStyleSheet(
            "QHeaderView::section { color: #34d399; }"
        )
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
        self.delete_income_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        income_btn_layout.addWidget(self.add_income_btn)
        income_btn_layout.addStretch()
        income_btn_layout.addWidget(self.delete_income_btn)
        income_layout.addLayout(income_btn_layout)
        income_group.setLayout(income_layout)
        layout.addWidget(income_group)

    def _connect_button_signals(
        self, prev_btn: QPushButton, next_btn: QPushButton
    ) -> None:
        prev_btn.clicked.connect(self.view_model.previous_month)
        next_btn.clicked.connect(self.view_model.next_month)
        self.archive_btn.clicked.connect(self.on_archive_month)
        self.edit_balance_btn.clicked.connect(self.on_edit_balance)
        self.add_bill_btn.clicked.connect(self.on_add_bill)
        self.delete_bill_btn.clicked.connect(self.on_delete_bill)
        self.add_income_btn.clicked.connect(self.on_add_income)
        self.delete_income_btn.clicked.connect(self.on_delete_income)
