"""Every colour the application paints, named once.

This module is the single source of truth for colour VALUES. Nothing else in
the tree may hold a hex literal; `tests/structural/test_colour_source.py` fails
the build if one appears. What a colour is FOR stays where it was: `ui.theme_tokens`
maps these onto semantic tokens per theme, `installer.ui.themes` maps them for the
installer; `application.reporting` maps them for an exported report.

Those three used to hold their own literals, which is how one hex came to serve
unrelated roles with nobody able to see it. The focus ring and the chart's
positive bars shared a value, so recolouring either silently moved the other;
the report mirrored thirty-one values by hand and drifted.

Names describe what a colour IS, never what it is used for, so a name does not
go stale when a role is repainted. Each is its hue family, prefixed MUTED_ below
40% saturation and suffixed with its lightness; under 14% saturation no hue
survives, so it is a GREY. The trailing comment on each line is that colour's
measured HSL, which is the language these decisions actually get argued in: the
safe state left green because the green sat at 52% lightness, not over its hue.

No Qt and no I/O, so the reporting layer can import it without reaching up into
the UI. That import is the whole point.
"""

from __future__ import annotations

# Grey. Neutral. Under 14% saturation, so no hue survives to read as a colour.
GREY_05 = "#0a0a0d"  # h240 s13% l5%
GREY_46 = "#6b7280"  # h220 s9% l46%
GREY_65 = "#9ca3af"  # h218 s11% l65%
GREY_84 = "#d1d5db"  # h216 s12% l84%
GREY_91 = "#e5e7eb"  # h220 s13% l91%
GREY_96 = "#f4f4f4"  # h0 s0% l96%
GREY_100 = "#ffffff"  # h0 s0% l100%

# Red. Danger, plus the deep fills a danger control sits on.
RED_24 = "#641717"  # h0 s63% l24%
RED_26 = "#6a1b21"  # h355 s59% l26%
RED_30 = "#7a1f25"  # h356 s59% l30%
RED_31 = "#7f1d1d"  # h0 s63% l31%
RED_35 = "#991b1b"  # h0 s70% l35%
RED_42 = "#b91c1c"  # h0 s74% l42%
RED_51 = "#dc2626"  # h0 s72% l51%
RED_71 = "#f87171"  # h0 s91% l71%
RED_94 = "#fee2e2"  # h0 s93% l94%

# Orange. Where the light theme takes warnings that amber cannot carry on white.
ORANGE_26 = "#78350f"  # h22 s78% l26%
ORANGE_37 = "#b45309"  # h26 s90% l37%
ORANGE_40 = "#c2410c"  # h17 s88% l40%
ORANGE_44 = "#d97706"  # h32 s95% l44%
ORANGE_48 = "#ea580c"  # h21 s90% l48%
ORANGE_61 = "#fb923c"  # h27 s96% l61%

# Amber. Caution, plus the within-facility state a bar takes below zero.
AMBER_50 = "#f59e0b"  # h38 s92% l50%
AMBER_56 = "#fbbf24"  # h43 s96% l56%
AMBER_89 = "#fef3c7"  # h48 s96% l89%


# Cyan. Info, plus the chart line that carries no verdict.
CYAN_48 = "#0ea5e9"  # h199 s89% l48%
CYAN_50 = "#00d4ff"  # h190 s100% l50%

# Sky. The light theme's deeper blues.
SKY_27 = "#075985"  # h201 s90% l27%
SKY_32 = "#0369a1"  # h201 s96% l32%

# Blue. The largest family: every dark surface, the muted greys with a blue
# cast, the primary action colour.
MUTED_BLUE_11 = "#111827"  # h221 s39% l11%
MUTED_BLUE_17 = "#1f2937"  # h215 s28% l17%
MUTED_BLUE_18 = "#242938"  # h225 s22% l18%
MUTED_BLUE_22 = "#2d3344"  # h224 s20% l22%
BLUE_25 = "#1e3a5f"  # h214 s52% l25%
# Two colours share a family and a rounded lightness, so the hue settles them.
# The name still comes only from the measurement.
MUTED_BLUE_27_H215 = "#334155"  # h215 s19% l27%
MUTED_BLUE_27_H217 = "#374151"  # h217 s19% l27%
MUTED_BLUE_28 = "#3a4156"  # h225 s19% l28%
MUTED_BLUE_35 = "#475569"  # h215 s19% l35%
MUTED_BLUE_42 = "#4f6885"  # h212 s25% l42%
BLUE_45 = "#2f4bb8"  # h228 s59% l45%
MUTED_BLUE_47 = "#64748b"  # h215 s16% l47%
MUTED_BLUE_48 = "#5b7799"  # h213 s25% l48%
BLUE_48 = "#1d4ed8"  # h224 s76% l48%
BLUE_53 = "#2563eb"  # h221 s83% l53%
MUTED_BLUE_55 = "#6b89ab"  # h212 s28% l55%
BLUE_56 = "#4a68d6"  # h227 s63% l56%
BLUE_68 = "#60a5fa"  # h213 s94% l68%
BLUE_78 = "#93c5fd"  # h212 s96% l78%
MUTED_BLUE_84 = "#cbd5e1"  # h213 s27% l84%
BLUE_87 = "#bfdbfe"  # h213 s97% l87%
MUTED_BLUE_88 = "#dbe0e8"  # h217 s22% l88%
MUTED_BLUE_96 = "#f3f4f6"  # h220 s14% l96%

# Indigo. The near-blacks the app and its installer are built on, plus a chart series.
MUTED_INDIGO_09 = "#0f1220"  # h229 s36% l9%
MUTED_INDIGO_12 = "#161827"  # h233 s28% l12%
MUTED_INDIGO_19 = "#24283b"  # h230 s24% l19%
MUTED_INDIGO_22 = "#2b2f44"  # h230 s23% l22%
MUTED_INDIGO_24 = "#2b3050"  # h232 s30% l24%
INDIGO_55 = "#3b5bdb"  # h228 s69% l55%
INDIGO_59 = "#4f46e5"  # h243 s75% l59%
MUTED_INDIGO_71 = "#a3a8c9"  # h232 s26% l71%
INDIGO_74 = "#818cf8"  # h234 s89% l74%

# Violet. The safe state and the accent, since safe stopped being green.
MUTED_VIOLET_25 = "#3b2f52"  # h261 s27% l25%
MUTED_VIOLET_45 = "#6b4c9a"  # h264 s34% l45%
VIOLET_74 = "#b8a1d9"  # h265 s42% l74%
VIOLET_85 = "#d8b4fe"  # h269 s97% l85%
VIOLET_95 = "#ede9fe"  # h251 s91% l95%

# Purple. The light theme's accent.
PURPLE_47 = "#7e22ce"  # h272 s72% l47%

# Fuchsia. The multi-series curve, which stays outside the series palette so
# it never reads as one more card.
FUCHSIA_40 = "#a21caf"  # h295 s72% l40%
FUCHSIA_73 = "#e879f9"  # h292 s91% l73%

# Pink. A series.
PINK_51 = "#db2777"  # h333 s71% l51%
PINK_70 = "#f472b6"  # h329 s86% l70%
