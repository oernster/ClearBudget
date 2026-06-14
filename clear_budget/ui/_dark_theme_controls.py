"""Control sub-styling for the dark theme - spin buttons, date edit, calendar.

Extracted from dark_theme to keep each module under the 400-LOC limit. These
rules use literal colours only (no template placeholders), so they live in a
plain string and are spliced into the main stylesheet.
"""


def control_qss() -> str:
    """QSS for spin-box buttons, the date edit and the calendar popup."""
    return """
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #3a4156;
    border-top-right-radius: 4px;
    background-color: #2d3344;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #3a4156;
    border-bottom-right-radius: 4px;
    background-color: #2d3344;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #3a4156;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #e5e7eb;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #e5e7eb;
}

QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {
    border-bottom-color: #6b7280;
}

QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {
    border-top-color: #6b7280;
}

QDateEdit {
    background-color: #242938;
    color: #e5e7eb;
    border: 1px solid #3a4156;
    border-radius: 4px;
    padding: 4px 8px;
}

QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid #3a4156;
}

QDateEdit::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #e5e7eb;
}

QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #1a1f2e;
}

QCalendarWidget QToolButton {
    color: #e5e7eb;
    background-color: transparent;
    padding: 4px 8px;
}

QCalendarWidget QToolButton:hover {
    background-color: #3a4156;
    border-radius: 4px;
}

QCalendarWidget QMenu {
    background-color: #242938;
    color: #e5e7eb;
}

QCalendarWidget QSpinBox {
    background-color: #242938;
    color: #e5e7eb;
}

QCalendarWidget QAbstractItemView {
    background-color: #242938;
    color: #e5e7eb;
    selection-background-color: #2dd4bf;
    selection-color: #0b0f17;
    outline: none;
}

QCalendarWidget QAbstractItemView:disabled {
    color: #6b7280;
}
"""
