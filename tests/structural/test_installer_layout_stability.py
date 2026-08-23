"""The installer's controls must not move while an operation runs.

The progress bar is hidden until work starts. A hidden widget normally leaves
the layout entirely, so its height went with it: the install directory, the
three checkboxes and every button jumped 26 pixels up the moment an operation
began and dropped back when it finished. Buttons moving under the pointer
mid-install is the worst possible moment for it.

The progress label had a smaller version of the same fault. It alternates
between a worker message and an empty string; an empty QLabel is shorter
than a filled one, so the column above it shifted by a pixel each time a
message arrived or cleared.

Both are fixed by reserving space rather than by watching for the symptom;
both are asserted here by source scan because the suite is Qt-free (see
tests/conftest.py) and `installer/ui` is outside the coverage gate, so nothing
else would notice either one coming back. The measurements themselves come
from an offscreen probe.
"""

import ast
from pathlib import Path

_BUILD = (
    Path(__file__).resolve().parents[2] / "installer" / "ui" / "_main_window_build.py"
)
_SAFE_LABEL = (
    Path(__file__).resolve().parents[2] / "installer" / "ui" / "_safe_label.py"
)


def _called_attrs(source: str) -> set[str]:
    """Every attribute called anywhere in `source`."""
    return {
        node.func.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_the_progress_bar_keeps_its_space_while_hidden():
    calls = _called_attrs(_BUILD.read_text(encoding="utf-8"))
    assert "setRetainSizeWhenHidden" in calls, (
        "the progress bar must reserve its height while hidden; showing it "
        "shifts every control below the status line"
    )


def test_the_progress_label_has_a_pinned_height():
    calls = _called_attrs(_BUILD.read_text(encoding="utf-8"))
    assert "setFixedHeight" in calls, (
        "the progress label alternates with an empty string, so its height "
        "must be pinned or the column above it moves"
    )


def test_the_pinned_height_is_measured_rather_than_a_literal():
    """A literal would be wrong at another DPI or text scale."""
    source = _BUILD.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setFixedHeight"
        ):
            continue
        assert node.args, "setFixedHeight called with no argument"
        assert not isinstance(node.args[0], ast.Constant), (
            "the progress label's height must be measured from the font, "
            "never a hardcoded pixel count"
        )
        return
    raise AssertionError("no setFixedHeight call found")


def test_safe_label_can_report_one_line_of_its_own_text():
    """The buffer belongs to SafeLabel, so the measurement does too."""
    names = {
        node.name
        for node in ast.walk(ast.parse(_SAFE_LABEL.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef)
    }
    assert "line_height" in names
