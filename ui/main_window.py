from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton
)
from PySide6.QtCore import Qt
from datetime import datetime
from ui.views.month_view import MonthView
from ui.views.solvency_panel import SolvencyPanel
from ui.views.credit_card_view import CreditCardView
from ui.views.archive_view import ArchiveView

class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("ClearBudget")
        self.setGeometry(100, 100, 1200, 800)

        # Current month (default to June 2026)
        self.current_month = "2026-06"

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()

        # Solvency panel at top
        self.solvency_panel = SolvencyPanel(db, self.current_month)
        layout.addWidget(self.solvency_panel)

        # Tabs
        tabs = QTabWidget()

        self.month_view = MonthView(db, self.current_month, self.on_month_changed)
        self.credit_card_view = CreditCardView(db, self.current_month)
        self.archive_view = ArchiveView(db)

        tabs.addTab(self.month_view, "Month View")
        tabs.addTab(self.credit_card_view, "Credit Cards")
        tabs.addTab(self.archive_view, "Archive")

        layout.addWidget(tabs)
        main_widget.setLayout(layout)

    def on_month_changed(self, year_month):
        """Called when user changes month."""
        self.current_month = year_month
        self.solvency_panel.update_month(year_month)
        self.credit_card_view.update_month(year_month)
