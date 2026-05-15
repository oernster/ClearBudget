import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from models.database import Database

def main():
    app = QApplication(sys.argv)

    # Initialize database
    db_path = Path.home() / '.clearbudget' / 'budget.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(str(db_path))

    # Create and show main window
    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
