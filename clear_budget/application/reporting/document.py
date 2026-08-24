"""The HTML page every exported report is wrapped in. No Qt, no I/O.

One self-contained document: the stylesheet is inline and the charts are
inline SVG, so the file opens anywhere with nothing beside it, survives being
emailed and needs no network round trip. Fixed dark palette matching the
app's own dark theme, rather than following whichever theme is active; see
chart_svg.
"""

from __future__ import annotations

from string import Template

from clear_budget.application.formatting import money_from_pence
from clear_budget.shared import palette

_STYLE_TEMPLATE = Template("""
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 24px;
  background: $GREY_05; color: $GREY_91;
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.55;
}
main { max-width: 960px; margin: 0 auto; }
header { border-bottom: 2px solid $MUTED_BLUE_28; padding-bottom: 14px;
         margin-bottom: 26px; }
h1 { font-size: 24px; margin: 0 0 4px; color: $VIOLET_85; }
h2 { font-size: 18px; margin: 30px 0 10px; color: $VIOLET_85; }
.subtitle { color: $GREY_65; margin: 0; }
section { background: $MUTED_BLUE_18; border: 1px solid $MUTED_BLUE_28;
          border-radius: 10px;
          padding: 18px 20px; margin-bottom: 22px; }
p { margin: 0 0 12px; }
p.note { color: $GREY_65; font-size: 14px; }
figure { margin: 0; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: right; padding: 7px 10px;
         border-bottom: 1px solid $MUTED_BLUE_28; }
th:first-child, td:first-child { text-align: left; }
thead th { color: $GREY_65; font-weight: 600; border-bottom: 2px solid $MUTED_BLUE_28; }
tbody tr:last-child td { border-bottom: none; }
.figures { display: flex; flex-wrap: wrap; gap: 26px; margin: 0 0 6px; padding: 0;
           list-style: none; }
.figures div { min-width: 130px; }
.figures dt { color: $GREY_65; font-size: 13px; }
.figures dd { margin: 0; font-size: 20px; font-weight: 600; }
.state { font-weight: 600; }
.state-safe { color: $VIOLET_74; }
.state-caution { color: $AMBER_56; }
.state-red { color: $RED_71; }
footer { color: $GREY_65; font-size: 13px; text-align: center; margin-top: 30px; }
@media print {
  /* Keep the dark identity when printed rather than dropping to a white page
     with unreadable pale text. */
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  section { break-inside: avoid; }
}
""")

# CSS is full of braces, so a $-placeholder template rather than an f-string.
_STYLES = _STYLE_TEMPLATE.substitute(vars(palette))
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
    """Format pence in the active currency, with a sign for a negative.

    An alias onto the one money formatter, kept here because the report modules
    import it from this module. A report and the screen render a figure
    identically; they used to differ.
    """
    return money_from_pence(pence)


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
