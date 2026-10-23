"""Post the CI report comment on a pull request.

Reads the files `make` leaves in reports/ (see the Makefile), renders one
Markdown comment, deletes this token's earlier report comments on the PR, and
posts the new one. Runs as the `report` step of .woodpecker/ci.yml; see
docs/ci.md. Standard library only, so it runs without `uv sync`.
"""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

MARKER = "<!-- immich-folder-organizer-ci -->"
LOG_LINES = 40
API = "https://api.github.com"


@dataclass
class Check:
    """One check's outcome: status is None when it never ran."""

    status: int | None
    log: str = ""


@dataclass
class Tests:
    total: int
    failed: int
    skipped: int

    @property
    def passed(self) -> int:
        return self.total - self.failed - self.skipped


@dataclass
class Coverage:
    covered: int
    valid: int

    @property
    def percent(self) -> float:
        return 100 * self.covered / self.valid if self.valid else 100.0


@dataclass
class FileCoverage:
    path: str
    covered: int
    missed_lines: list[int]

    @property
    def total(self) -> int:
        return self.covered + len(self.missed_lines)


@dataclass
class Reports:
    checks: dict[str, Check]
    tests: Tests | None
    coverage: Coverage | None
    changed: list[FileCoverage] = field(default_factory=list)
    image_bytes: int | None = None
    base_tests: Tests | None = None
    base_coverage: Coverage | None = None


# Report name in reports/ -> label in the comment, in display order
CHECKS = {
    "lint": "Lint",
    "format": "Format",
    "types": "Types",
    "test": "Tests",
    "image": "Docker image",
}
# Checks whose useful output is at the end of the log, not the start
TAIL_LOGS = {"test", "image"}


def _read(path: Path) -> str | None:
    return path.read_text() if path.exists() else None


def _load_tests(path: Path) -> Tests | None:
    if not path.exists():
        return None
    total = failed = skipped = 0
    for suite in ET.parse(path).getroot().iter("testsuite"):
        total += int(suite.get("tests", 0))
        failed += int(suite.get("failures", 0)) + int(suite.get("errors", 0))
        skipped += int(suite.get("skipped", 0))
    return Tests(total, failed, skipped)


def _load_coverage(path: Path) -> Coverage | None:
    if not path.exists():
        return None
    root = ET.parse(path).getroot()
    return Coverage(int(root.get("lines-covered", 0)), int(root.get("lines-valid", 0)))


def load(reports_dir: Path) -> Reports:
    checks = {}
    for name in CHECKS:
        status = _read(reports_dir / f"{name}.status")
        checks[name] = Check(
            int(status) if status is not None else None,
            _read(reports_dir / f"{name}.log") or "",
        )

    changed = []
    diff = _read(reports_dir / "diff-cover.json")
    if diff is not None:
        for path, stats in sorted(json.loads(diff)["src_stats"].items()):
            changed.append(
                FileCoverage(
                    path, len(stats["covered_lines"]), sorted(stats["violation_lines"])
                )
            )

    size = _read(reports_dir / "image.size")
    return Reports(
        checks=checks,
        tests=_load_tests(reports_dir / "junit.xml"),
        coverage=_load_coverage(reports_dir / "coverage.xml"),
        changed=changed,
        image_bytes=int(size) if size else None,
        base_tests=_load_tests(reports_dir / "base" / "junit.xml"),
        base_coverage=_load_coverage(reports_dir / "base" / "coverage.xml"),
    )


def color(percent: float) -> str:
    if percent >= 80:
        return "🟢"
    if percent >= 60:
        return "🟡"
    return "🔴"


def badge(percent: float) -> str:
    """Color and a ten-segment bar, e.g. 🟢 ▰▰▰▰▰▰▰▰▰▱."""
    filled = int(percent / 10 + 0.5)
    return f"{color(percent)} {'▰' * filled}{'▱' * (10 - filled)}"


def line_ranges(lines: list[int]) -> str:
    """[1, 2, 3, 5] -> '1-3, 5'."""
    runs: list[list[int]] = []
    for n in lines:
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    return ", ".join(f"{r[0]}-{r[-1]}" if len(r) > 1 else f"{r[0]}" for r in runs)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _count(log: str, pattern: str) -> int | None:
    match = re.search(pattern, log)
    return int(match.group(1)) if match else None


def _failure_detail(name: str, reports: Reports) -> str:
    log = reports.checks[name].log
    if name == "lint":
        n = _count(log, r"Found (\d+) error")
        return f" {_plural(n, 'finding')}" if n is not None else ""
    if name == "format":
        n = _count(log, r"(\d+) files? would be reformatted")
        return f" {_plural(n, 'file')}" if n is not None else ""
    if name == "types":
        n = _count(log, r"Found (\d+) error")
        return f" {_plural(n, 'error')}" if n is not None else ""
    if name == "image":
        return " build failed"
    return ""


def _tests_summary(reports: Reports) -> str:
    tests = reports.tests
    if tests is None:
        return " no results"
    parts = [f"{tests.passed} passed"]
    if tests.failed:
        parts.append(f"{tests.failed} failed")
    if tests.skipped:
        parts.append(f"{tests.skipped} skipped")
    summary = " " + ", ".join(parts)
    if reports.base_tests is not None:
        delta = tests.total - reports.base_tests.total
        summary += f" ({f'{delta:+d}' if delta else '±0'} vs base)"
    return summary


def _check_cell(name: str, reports: Reports) -> str:
    check = reports.checks[name]
    if check.status is None:
        return "⚪ not run"
    if name == "test":
        return ("✅" if check.status == 0 else "❌") + _tests_summary(reports)
    if check.status != 0:
        return "❌" + _failure_detail(name, reports)
    if name == "image" and reports.image_bytes is not None:
        return f"✅ builds, {round(reports.image_bytes / 1_000_000)} MB"
    return "✅"


def _excerpt(name: str, log: str) -> str:
    lines = log.splitlines(keepends=True)
    if len(lines) <= LOG_LINES:
        return "".join(lines)
    hidden = len(lines) - LOG_LINES
    if name in TAIL_LOGS:
        return f"… {hidden} earlier lines\n" + "".join(lines[-LOG_LINES:])
    return "".join(lines[:LOG_LINES]) + f"… {hidden} more lines\n"


def render(reports: Reports, git_stats: dict[str, int], env: dict[str, str]) -> str:
    ok = all(c.status == 0 for c in reports.checks.values())
    out = [MARKER, f"## {'✅ CI passed' if ok else '❌ CI failed'}", ""]

    out += ["| Check | Result |", "|---|---|"]
    out += [
        f"| {label} | {_check_cell(name, reports)} |" for name, label in CHECKS.items()
    ]

    out += ["", "### Coverage", "", "| Scope | Coverage |", "|---|---|"]
    lines = sum(f.total for f in reports.changed)
    if lines:
        covered = sum(f.covered for f in reports.changed)
        percent = 100 * covered / lines
        out.append(
            f"| Changed lines | {badge(percent)} {percent:.1f}% ({covered}/{lines}) |"
        )
    else:
        out.append("| Changed lines | no changed Python lines |")
    if reports.coverage is not None:
        total = f"{reports.coverage.percent:.1f}%"
        if reports.base_coverage is not None:
            total += (
                f" ({reports.coverage.percent - reports.base_coverage.percent:+.1f})"
            )
        else:
            total += " (base n/a)"
        out.append(f"| Total lines | {total} |")

    if lines:
        out += [
            "",
            "### Changed files",
            "",
            "| File | Changed lines | Uncovered |",
            "|---|---|---|",
        ]
        for f in reports.changed:
            if f.total:
                percent = 100 * f.covered / f.total
                out.append(
                    f"| `{f.path}` | {color(percent)} {percent:.1f}% ({f.covered}/{f.total}) "
                    f"| {line_ranges(f.missed_lines)} |"
                )

    out += [
        "",
        "### This PR",
        "",
        (
            f"{_plural(git_stats['files'], 'file')} changed, "
            f"+{git_stats['insertions']} / −{git_stats['deletions']}, "
            f"{_plural(git_stats['commits'], 'commit')}"
        ),
    ]

    for name, label in CHECKS.items():
        check = reports.checks[name]
        if check.status not in (None, 0) and check.log:
            out += [
                "",
                f"<details><summary>{label} output</summary>",
                "",
                "```",
                _excerpt(name, check.log).rstrip("\n"),
                "```",
                "</details>",
            ]

    sha = env.get("CI_COMMIT_SHA", "")[:7]
    out += ["", "---", f"[pipeline]({env.get('CI_PIPELINE_URL', '')}) · `{sha}`", ""]
    return "\n".join(out)


def git_stats(base: str) -> dict[str, int]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        ).stdout

    shortstat = git("diff", "--shortstat", f"{base}...HEAD")
    return {
        "files": _count(shortstat, r"(\d+) files? changed") or 0,
        "insertions": _count(shortstat, r"(\d+) insertion") or 0,
        "deletions": _count(shortstat, r"(\d+) deletion") or 0,
        "commits": int(git("rev-list", "--count", f"{base}..HEAD")),
    }


def _request(method: str, path: str, token: str, body: dict | None = None):
    """Call the GitHub API, retrying 5xx and connection errors."""
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(4):
        req = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code < 500:
                print(
                    f"GitHub refused {method} {path}: {e.code} {e.read().decode(errors='replace')}"
                )
                accepted = e.headers.get("x-accepted-github-permissions")
                if accepted:
                    print(f"x-accepted-github-permissions: {accepted}")
                raise SystemExit(1) from e
            error: Exception = e
        except urllib.error.URLError as e:
            error = e
        if attempt == 3:
            raise SystemExit(f"GitHub {method} {path} failed after retries: {error}")
        time.sleep(2**attempt)


def replace_comment(repo: str, pr: str, body: str, token: str) -> None:
    """Delete this token's earlier report comments on the PR, then post body."""
    login = _request("GET", "/user", token)["login"]
    # Collect every page before deleting, since deleting shifts later pages
    ours, page = [], 1
    while comments := _request(
        "GET", f"/repos/{repo}/issues/{pr}/comments?per_page=100&page={page}", token
    ):
        ours += [
            c["id"]
            for c in comments
            if MARKER in c["body"] and c["user"]["login"] == login
        ]
        page += 1
    for comment_id in ours:
        _request("DELETE", f"/repos/{repo}/issues/comments/{comment_id}", token)
    posted = _request(
        "POST", f"/repos/{repo}/issues/{pr}/comments", token, {"body": body}
    )
    print(f"Posted {posted['html_url']}")


def main() -> None:
    env = dict(os.environ)
    body = render(
        load(Path("reports")),
        git_stats(f"origin/{env['CI_COMMIT_TARGET_BRANCH']}"),
        env,
    )
    print(body)
    # A secret stored from a file keeps its trailing newline
    token = env["GITHUB_TOKEN"].strip()
    replace_comment(env["CI_REPO"], env["CI_COMMIT_PULL_REQUEST"], body, token)


if __name__ == "__main__":
    main()
