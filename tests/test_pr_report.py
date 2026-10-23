"""Tests for scripts/ci/pr_report.py: rendering the CI comment from report files."""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "pr_report", Path(__file__).parent.parent / "scripts" / "ci" / "pr_report.py"
)
assert _spec and _spec.loader
pr_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr_report)

ENV = {
    "CI_PIPELINE_URL": "https://ci.example/repos/7/pipeline/42",
    "CI_COMMIT_SHA": "0123456789abcdef",
}
GIT = {"files": 3, "insertions": 40, "deletions": 5, "commits": 2}


def _coverage_xml(valid: int, covered: int) -> str:
    return (
        f'<?xml version="1.0" ?><coverage lines-valid="{valid}" '
        f'lines-covered="{covered}" line-rate="{covered / valid:.4f}"></coverage>'
    )


def _junit_xml(tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite '
        f'tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">'
        "</testsuite></testsuites>"
    )


def _diff_cover(src_stats: dict) -> str:
    lines = sum(
        len(s["covered_lines"]) + len(s["violation_lines"]) for s in src_stats.values()
    )
    misses = sum(len(s["violation_lines"]) for s in src_stats.values())
    return json.dumps(
        {
            "total_num_lines": lines,
            "total_num_violations": misses,
            "total_percent_covered": round(100 * (lines - misses) / lines)
            if lines
            else 100,
            "src_stats": src_stats,
        }
    )


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    """A reports/ directory for an all-green PR run, with a base to compare to."""
    files = {
        "lint.status": "0",
        "lint.log": "All checks passed!\n",
        "format.status": "0",
        "format.log": "31 files already formatted\n",
        "types.status": "0",
        "types.log": "Success: no issues found in 23 source files\n",
        "test.status": "0",
        "test.log": "103 passed\n",
        "junit.xml": _junit_xml(105, skipped=1),
        "coverage.xml": _coverage_xml(400, 370),
        "diff-cover.json": _diff_cover(
            {
                "immich_folder_organizer/config.py": {
                    "covered_lines": list(range(1, 35)),
                    "violation_lines": [40, 41, 42, 50, 51, 60],
                },
            }
        ),
        "image.status": "0",
        "image.log": "Successfully built abc\n",
        "image.size": "324000000",
        "base/junit.xml": _junit_xml(103),
        "base/coverage.xml": _coverage_xml(400, 368),
    }
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(body)
    return tmp_path


def render(reports_dir: Path) -> str:
    return pr_report.render(pr_report.load(reports_dir), GIT, ENV)


def test_all_green(reports):
    body = render(reports)
    assert body.startswith(pr_report.MARKER)
    assert "## ✅ CI passed" in body
    assert "| Lint | ✅ |" in body
    assert "| Format | ✅ |" in body
    assert "| Types | ✅ |" in body
    assert "| Tests | ✅ 104 passed, 1 skipped (+2 vs base) |" in body
    assert "| Docker image | ✅ builds, 324 MB |" in body
    assert "| Changed lines | 🟢 ▰▰▰▰▰▰▰▰▰▱ 85.0% (34/40) |" in body
    assert "| Total lines | 92.5% (+0.5) |" in body
    assert (
        "| `immich_folder_organizer/config.py` | 🟢 85.0% (34/40) | 40-42, 50-51, 60 |"
        in body
    )
    assert "3 files changed, +40 / −5, 2 commits" in body
    assert "<details>" not in body
    assert "[pipeline](https://ci.example/repos/7/pipeline/42)" in body
    assert "`0123456`" in body


def test_failing_checks_show_counts_and_logs(reports):
    (reports / "lint.status").write_text("1")
    (reports / "lint.log").write_text(
        "F401 [*] `os` imported but unused\n --> x.py:1:8\nFound 3 errors.\n"
    )
    (reports / "format.status").write_text("1")
    (reports / "format.log").write_text(
        "Would reformat: x.py\n2 files would be reformatted, 29 files already formatted\n"
    )
    (reports / "types.status").write_text("1")
    (reports / "types.log").write_text(
        "x.py:1: error: bad\nFound 1 error in 1 file (checked 23 source files)\n"
    )
    (reports / "test.status").write_text("1")
    (reports / "junit.xml").write_text(_junit_xml(103, failures=2, errors=1))
    (reports / "image.status").write_text("1")
    (reports / "image.size").unlink()

    body = render(reports)
    assert "## ❌ CI failed" in body
    assert "| Lint | ❌ 3 findings |" in body
    assert "| Format | ❌ 2 files |" in body
    assert "| Types | ❌ 1 error |" in body
    assert "| Tests | ❌ 100 passed, 3 failed (±0 vs base) |" in body
    assert "| Docker image | ❌ build failed |" in body
    assert body.count("<details>") == 5
    assert "F401 [*] `os` imported but unused" in body


def test_long_log_is_truncated(reports):
    (reports / "lint.status").write_text("1")
    (reports / "lint.log").write_text(
        "".join(f"line {i}\n" for i in range(100)) + "Found 100 errors.\n"
    )
    body = render(reports)
    assert "line 39\n" in body
    assert "line 40\n" not in body
    assert "61 more lines" in body


def test_checks_that_never_ran(reports):
    for name in [
        "types.status",
        "types.log",
        "image.status",
        "image.log",
        "image.size",
    ]:
        (reports / name).unlink()
    body = render(reports)
    assert "| Types | ⚪ not run |" in body
    assert "| Docker image | ⚪ not run |" in body
    assert "## ❌ CI failed" in body


def test_base_unavailable(reports):
    for name in ["base/junit.xml", "base/coverage.xml"]:
        (reports / name).unlink()
    body = render(reports)
    assert "| Tests | ✅ 104 passed, 1 skipped |" in body
    assert "| Total lines | 92.5% (base n/a) |" in body


def test_no_changed_lines(reports):
    (reports / "diff-cover.json").write_text(_diff_cover({}))
    body = render(reports)
    assert "| Changed lines | no changed Python lines |" in body
    assert "Changed files" not in body


@pytest.mark.parametrize(
    "percent, color",
    [
        (100.0, "🟢"),
        (80.0, "🟢"),
        (79.9, "🟡"),
        (60.0, "🟡"),
        (59.9, "🔴"),
        (0.0, "🔴"),
    ],
)
def test_thresholds(percent, color):
    assert pr_report.badge(percent).startswith(color)


def test_line_ranges():
    assert pr_report.line_ranges([1, 2, 3, 5, 7, 8]) == "1-3, 5, 7-8"
    assert pr_report.line_ranges([]) == ""
