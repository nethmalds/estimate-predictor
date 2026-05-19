"""Root pytest plugin — auto-updates TEST_PLAN.md after every test session.

Hooks into pytest's normal run lifecycle:
- ``pytest_runtest_logreport`` collects pass/fail/xfail/skip per test.
- ``pytest_sessionfinish`` discovers which BE-TC-XXX comment belongs to each
  test function, then rewrites the Status column and summary totals in
  tests/TEST_PLAN.md.

No configuration needed — just run pytest as usual:
    pytest tests/                                   # full suite
    pytest tests/integration/03_form_submission_api # single module
"""
from __future__ import annotations

import ast
import re
from datetime import date
from pathlib import Path

_TESTS   = Path(__file__).resolve().parent
_BACKEND = _TESTS.parent
_PLAN    = _TESTS / "TEST_PLAN.md"

SYM_PASS       = "✅ Pass"
SYM_FAIL       = "❌ Fail"
SYM_NOT_TESTED = "⚠️ Not Tested"
_SYMS          = (SYM_PASS, SYM_FAIL, SYM_NOT_TESTED)
_ROW_RE        = re.compile(r"^\|\s*(BE-TC-\d+)\s*\|")

# ── Session-level state ───────────────────────────────────────────────────────

_tc_map:  dict[str, str] = {}   # {BE-TC-XXX: node_id} — populated at session start
_results: dict[str, str] = {}   # {node_id: status}    — populated during run


def pytest_sessionstart(session) -> None:  # noqa: ANN001
    """Discover TC → test-function mapping before any tests run.

    Doing this at start (not finish) avoids triggering async-cleanup warnings
    from ast.parse() while the event loop is being torn down.
    """
    global _tc_map  # noqa: PLW0603
    if _PLAN.exists():
        _tc_map = _discover_tc_mapping()


def pytest_runtest_logreport(report) -> None:  # noqa: ANN001
    nid = report.nodeid
    if report.when == "call":
        if hasattr(report, "wasxfail"):
            _results[nid] = "xfail"
        elif report.passed:
            _results[nid] = "pass"
        elif report.failed:
            _results[nid] = "fail"
        elif report.skipped:
            _results[nid] = "skip"
    elif report.when == "setup" and report.failed:
        _results.setdefault(nid, "error")


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ANN001
    # Update on normal exits only — 0 (all pass) or 1 (some failures).
    # exitstatus 2+ means a collection error or crash; plan would be stale.
    if exitstatus > 1 or not _results or not _tc_map or not _PLAN.exists():
        return

    tc_statuses = _resolve(_tc_map, _results)
    if not tc_statuses:
        return

    updated = _update_plan(tc_statuses)
    resolved = len(tc_statuses)
    print(
        f"\n  [test-plan] {resolved} TC(s) checked, "
        f"{updated} row(s) updated -> tests/TEST_PLAN.md"
    )


# ── TC discovery ──────────────────────────────────────────────────────────────


def _discover_tc_mapping() -> dict[str, str]:
    """Scan test files and return {BE-TC-XXX: pytest_node_id}.

    Algorithm:
    - Non-indented comment line containing ``BE-TC-N`` → map each extracted
      TC ID to the *n*-th test function that follows the comment line, in order.
      (Handles ``# ── BE-TC-060 & 061: ...`` → two consecutive functions.)
    - Indented comment (inside a function body) → map to the most recently
      opened test function before that line.
    """
    mapping: dict[str, str] = {}
    for py_file in sorted(_TESTS.rglob("test_*.py")):
        try:
            _extract(py_file, py_file.read_text(encoding="utf-8"), mapping)
        except Exception:  # noqa: BLE001
            pass
    return mapping


def _collect_funcs(tree: ast.Module) -> list[tuple[str | None, str, int, int]]:
    """Return ``(class_or_None, func_name, 1-based lineno, col_offset)`` for every test_* function."""
    out: list[tuple[str | None, str, int, int]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for item in ast.iter_child_nodes(node):
                if (
                    isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef))
                    and item.name.startswith("test_")
                ):
                    out.append((node.name, item.name, item.lineno, item.col_offset))
        elif (
            isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name.startswith("test_")
        ):
            out.append((None, node.name, node.lineno, node.col_offset))
    return sorted(out, key=lambda t: t[2])


def _extract(py_file: Path, text: str, mapping: dict[str, str]) -> None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return

    rel   = py_file.relative_to(_BACKEND).as_posix()
    funcs = _collect_funcs(tree)
    lines = text.splitlines()

    for i, raw in enumerate(lines):
        if "#" not in raw:
            continue
        comment = raw.split("#", 1)[1]
        # Capture "BE-TC-NNN" and any "& NNN" continuations on the same line
        # e.g. "BE-TC-005 & 006 & 007" → ["005", "006", "007"]
        nums = []
        for _m in re.finditer(r"BE-TC-(\d+)((?:\s*&\s*\d+)*)", comment):
            nums.append(_m.group(1))
            nums.extend(re.findall(r"\d+", _m.group(2) or ""))
        if not nums:
            continue

        tc_ids       = [f"BE-TC-{n}" for n in nums]
        comment_col  = len(raw) - len(raw.lstrip())  # indentation in characters
        lineno_1     = i + 1  # AST uses 1-based line numbers

        # Determine intent by comparing comment indentation to function definitions.
        #
        # col_offset == 0  → module-level comment → "before next function(s)"
        # col_offset == func col_offset  → class-level between-method comment
        #                                   → "before next function(s)"
        # col_offset > func col_offset   → inside a method body
        #                                   → "belongs to most recent function"
        #
        # We use the nearest function's col_offset as the reference.
        nearby = sorted(funcs, key=lambda f: abs(f[2] - lineno_1))
        ref_col = nearby[0][3] if nearby else 0

        if comment_col <= ref_col:
            # Module-level or class-level comment: map to next n functions
            after = [f for f in funcs if f[2] > lineno_1]
            for idx, tc_id in enumerate(tc_ids):
                if idx >= len(after):
                    break
                cls, fn = after[idx][0], after[idx][1]
                nid = f"{rel}::{cls}::{fn}" if cls else f"{rel}::{fn}"
                mapping.setdefault(tc_id, nid)
        else:
            # Body comment: map to the most recent function before this line
            prior = [f for f in funcs if f[2] < lineno_1]
            if not prior:
                continue
            cls, fn = prior[-1][0], prior[-1][1]
            nid = f"{rel}::{cls}::{fn}" if cls else f"{rel}::{fn}"
            for tc_id in tc_ids:
                mapping.setdefault(tc_id, nid)


# ── Resolve TC → status ───────────────────────────────────────────────────────


def _resolve(
    tc_map: dict[str, str],
    results: dict[str, str],
) -> dict[str, str]:
    """Return {tc_id: status} for every TC whose test was actually run."""
    out: dict[str, str] = {}
    for tc_id, node_id in tc_map.items():
        if node_id in results:
            out[tc_id] = results[node_id]
        else:
            # Suffix match — handles minor path discrepancies between OS / cwd
            suffix = node_id.split("::", 1)[-1] if "::" in node_id else node_id
            match  = next((v for k, v in results.items() if k.endswith(suffix)), None)
            if match is not None:
                out[tc_id] = match
    return out


# ── Update TEST_PLAN.md ───────────────────────────────────────────────────────


def _sym(status: str) -> str:
    if status == "pass":
        return SYM_PASS
    if status in ("fail", "error", "xfail"):
        return SYM_FAIL
    return SYM_NOT_TESTED


def _update_plan(tc_statuses: dict[str, str]) -> int:
    """Rewrite Status column for resolved TCs. Returns number of rows changed."""
    text  = _PLAN.read_text(encoding="utf-8")
    lines = text.splitlines()
    updated = 0
    out: list[str] = []

    for line in lines:
        m = _ROW_RE.match(line)
        if m and m.group(1) in tc_statuses:
            new_sym = _sym(tc_statuses[m.group(1)])
            cells   = line.split("|")
            for i, cell in enumerate(cells):
                if cell.strip() in _SYMS:
                    if cell.strip() != new_sym:
                        cells[i] = f" {new_sym} "
                        updated += 1
                    break
            line = "|".join(cells)
        out.append(line)

    # Refresh the "Last Updated" date
    today  = date.today().strftime("%Y-%m-%d")
    result = re.sub(
        r"(\*\*Last Updated:\*\*\s*)[\d\-]+[^\n]*",
        rf"\g<1>{today}",
        "\n".join(out),
    )

    result = _recompute_summary(result)
    _PLAN.write_text(result, encoding="utf-8")
    return updated


def _recompute_summary(text: str) -> str:
    """Recount statuses from the (already updated) body and overwrite summary table."""
    lines = text.splitlines()

    # Pass 1: count per section in document order
    section_order: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    current: str | None = None
    in_summary = False

    for line in lines:
        hm = re.match(r"^## \d+\.\s+(.+)", line)
        if hm:
            cat = hm.group(1).strip()
            if "Summary" in cat:
                in_summary = True
                current    = None
            else:
                in_summary = False
                current    = cat
                section_order.append(cat)
                counts[cat] = {"total": 0, "pass": 0, "fail": 0, "not_tested": 0}
            continue

        if in_summary or current is None or not _ROW_RE.match(line):
            continue

        cells = [c.strip() for c in line.split("|")]
        sym   = next((c for c in cells if c in _SYMS), None)
        if sym is None:
            continue

        c = counts[current]
        c["total"] += 1
        if sym == SYM_PASS:        c["pass"] += 1
        elif sym == SYM_FAIL:      c["fail"] += 1
        else:                      c["not_tested"] += 1

    if not counts:
        return text

    # Grand total
    grand: dict[str, int] = {"total": 0, "pass": 0, "fail": 0, "not_tested": 0}
    for c in counts.values():
        for k in grand:
            grand[k] += c[k]

    # Pass 2: rewrite summary rows in section order (avoids name-matching issues)
    summary_re  = re.compile(r"^\|\s*\*?\*?([^|*]+?)\*?\*?\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|")
    section_idx = 0
    new_lines: list[str] = []

    for line in lines:
        m = summary_re.match(line)
        if m:
            raw = m.group(1).strip()
            if raw.lower() == "total":
                line = (
                    f"| **Total** | **{grand['total']}** | "
                    f"**{grand['pass']}** | **{grand['fail']}** | **{grand['not_tested']}** |"
                )
            elif section_idx < len(section_order):
                c = counts[section_order[section_idx]]
                section_idx += 1
                line = f"| {raw} | {c['total']} | {c['pass']} | {c['fail']} | {c['not_tested']} |"
        new_lines.append(line)

    return "\n".join(new_lines)
