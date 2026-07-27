"""The HTML page every exported report is wrapped in. No Qt, no I/O.

One self-contained document: the stylesheet is inline and the charts are
inline SVG, so the file opens anywhere with nothing beside it, survives being
emailed and prints without a network round trip. Deliberately light and plain
rather than themed; see chart_svg for why a report does not follow the app's
dark mode.
"""

from __future__ import annotations

from clear_budget.shared.currency import get_symbol

_STYLES = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 24px;
  background: #f9fafb; color: #1f2937;
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.55;
}
main { max-width: 960px; margin: 0 auto; }
header { border-bottom: 2px solid #e5e7eb; padding-bottom: 14px; margin-bottom: 26px; }
h1 { font-size: 24px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 30px 0 10px; }
.subtitle { color: #6b7280; margin: 0; }
section { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
          padding: 18px 20px; margin-bottom: 22px; }
p { margin: 0 0 12px; }
p.note { color: #6b7280; font-size: 14px; }
figure { margin: 0; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid #e5e7eb; }
th:first-child, td:first-child { text-align: left; }
thead th { color: #6b7280; font-weight: 600; border-bottom: 2px solid #e5e7eb; }
tbody tr:last-child td { border-bottom: none; }
.figures { display: flex; flex-wrap: wrap; gap: 26px; margin: 0 0 6px; padding: 0;
           list-style: none; }
.figures div { min-width: 130px; }
.figures dt { color: #6b7280; font-size: 13px; }
.figures dd { margin: 0; font-size: 20px; font-weight: 600; }
.state { font-weight: 600; }
.state-safe { color: #059669; }
.state-caution { color: #b45309; }
.state-red { color: #dc2626; }
footer { color: #6b7280; font-size: 13px; text-align: center; margin-top: 30px; }
@media print {
  body { background: #fff; padding: 0; }
  section { break-inside: avoid; border-color: #d1d5db; }
}
"""

_FOOTER = "Exported from ClearBudget. Figures are projections, not statements."


def escape(text) -> str:
    """Escape the five characters that would otherwise break the markup."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def money(pence: int) -> str:
    """Format pence in the active currency, with a sign for a negative."""
    symbol = get_symbol()
    sign = "-" if pence < 0 else ""
    return f"{sign}{symbol}{abs(pence) / 100:,.2f}"


def document(*, title: str, subtitle: str, body: str) -> str:
    """Wrap `body` in the standard page."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{_STYLES}</style>\n</head>\n<body>\n<main>\n"
        f"<header>\n<h1>{escape(title)}</h1>\n"
        f'<p class="subtitle">{escape(subtitle)}</p>\n</header>\n'
        f"{body}\n"
        f"<footer>{escape(_FOOTER)}</footer>\n"
        "</main>\n</body>\n</html>\n"
    )
