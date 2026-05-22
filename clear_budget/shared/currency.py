"""Currency configuration - supported currencies and active symbol."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Currency:
    """A supported display currency."""

    code: str
    symbol: str
    name: str


# English-speaking countries / territories ordered by prominence.
CURRENCIES: list[Currency] = [
    Currency("GBP", "£", "British Pound"),
    Currency("USD", "$", "US Dollar"),
    Currency("EUR", "€", "Euro (Ireland / Malta)"),
    Currency("AUD", "A$", "Australian Dollar"),
    Currency("CAD", "C$", "Canadian Dollar"),
    Currency("NZD", "NZ$", "New Zealand Dollar"),
    Currency("ZAR", "R", "South African Rand"),
    Currency("SGD", "S$", "Singapore Dollar"),
    Currency("HKD", "HK$", "Hong Kong Dollar"),
    Currency("INR", "₹", "Indian Rupee"),
    Currency("NGN", "₦", "Nigerian Naira"),
    Currency("GHS", "₵", "Ghanaian Cedi"),
    Currency("KES", "KSh", "Kenyan Shilling"),
    Currency("PHP", "₱", "Philippine Peso"),
    Currency("PKR", "Rs", "Pakistani Rupee"),
    Currency("BDT", "৳", "Bangladeshi Taka"),
    Currency("JMD", "J$", "Jamaican Dollar"),
    Currency("TTD", "TT$", "Trinidad & Tobago Dollar"),
    Currency("NAD", "N$", "Namibian Dollar"),
    Currency("BWP", "P", "Botswanan Pula"),
    Currency("ZMW", "ZK", "Zambian Kwacha"),
    Currency("BZD", "BZ$", "Belize Dollar"),
    Currency("GYD", "G$", "Guyanese Dollar"),
    Currency("FJD", "FJ$", "Fijian Dollar"),
    Currency("PGK", "K", "Papua New Guinean Kina"),
]

_BY_CODE: dict[str, Currency] = {c.code: c for c in CURRENCIES}
DEFAULT_CURRENCY: Currency = CURRENCIES[0]  # GBP

_active: Currency = DEFAULT_CURRENCY


def get_currency() -> Currency:
    """Return the currently active Currency."""
    return _active


def get_symbol() -> str:
    """Return the symbol of the currently active currency."""
    return _active.symbol


def set_currency(code: str) -> None:
    """Activate the currency identified by *code* (falls back to GBP)."""
    global _active
    _active = _BY_CODE.get(code, DEFAULT_CURRENCY)
