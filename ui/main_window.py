from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QMenuBar,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from pathlib import Path
from datetime import datetime
from ui.views.month_view import MonthView
from ui.views.solvency_panel import SolvencyPanel
from ui.views.credit_card_view import CreditCardView
from ui.views.archive_view import ArchiveView
from ui.views.about_dialog import AboutDialog
from clear_budget.version import APP_NAME, __version__
from clear_budget.ui.dark_theme import DARK_QSS


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.setGeometry(100, 100, 1200, 800)

        # Set window icon
        icon_path = Path(__file__).resolve().parents[1] / "clearbudget_128.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Apply dark theme
        QApplication.instance().setStyleSheet(DARK_QSS)

        # Current month (default to June 2026)
        self.current_month = "2026-06"

        # Menu bar
        self._create_menu_bar()

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()

        # Solvency panel at top
        self.solvency_panel = SolvencyPanel(db, self.current_month)
        layout.addWidget(self.solvency_panel)

        # Centered icon strip above tabs
        icon_strip_widget = QWidget()
        icon_strip_widget.setFixedHeight(44)
        icon_strip = QHBoxLayout(icon_strip_widget)
        icon_strip.setContentsMargins(0, 4, 0, 4)
        nav_icon_label = QLabel()
        nav_icon_path = Path(__file__).resolve().parents[1] / "clearbudget_32.png"
        if nav_icon_path.exists():
            nav_pixmap = QPixmap(str(nav_icon_path))
            nav_icon_label.setPixmap(
                nav_pixmap.scaledToHeight(
                    32, Qt.TransformationMode.SmoothTransformation
                )
            )
        else:
            nav_icon_label.setText("ICON MISSING")
        nav_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_strip.addStretch()
        icon_strip.addWidget(nav_icon_label)
        icon_strip.addStretch()
        layout.addWidget(icon_strip_widget)

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

    def _create_menu_bar(self):
        """Create menu bar with File and Help menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)

    def _show_about(self):
        """Show About dialog."""
        dialog = AboutDialog(self)
        dialog.exec()
