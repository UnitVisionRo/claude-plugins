#!/usr/bin/env python3
"""Checks for scoped-tests.py. Run: python3 -B dev-workflow/hooks/test_scoped_tests.py"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).with_name("scoped-tests.py")
spec = importlib.util.spec_from_file_location("scoped_tests", HOOK)
scoped_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoped_tests)

BLOCKED = [
    "python -B -m pytest",
    "python -B -m pytest -n 4",
    "cd api && python -B -m pytest -x -q 2>&1 | tail -20",
    "uv run pytest",
    "pytest -m 'not db'",
    "python -B -m pytest tests",
    "python -B -m pytest tests/",
    "python -B -m pytest ./tests/ --durations=20",
    "TEST_DB_NAME=x_test python -B -m pytest -n 4",
    "timeout 600 python -B -m pytest",
    "sh -c 'python -m pytest'",
    "sh -c \"cd gui; npm test\"",
    "bash -lc \"cd gui && npm test\"",
    "cd api && bash -ec 'source .venv/bin/activate && python -B -m pytest -n 4'",
    "python -B -m pytest back/tests",
    "npx vitest run gui/test/",
    "npm test",
    "npm run test",
    "npm --prefix gui test",
    "npm run test:e2e",
    "npx vitest run",
    "npx vitest",
    "npx vitest run test/",
    "npx playwright test",
    "E2E_REUSE_BUILD=1 npm run test:e2e",
]

ALLOWED = [
    "FULL_SUITE=1 python -B -m pytest -n 4",
    "cd gui && FULL_SUITE=1 npm test",
    "FULL_SUITE=1 TEST_DB_NAME=x_test npm run test:e2e",
    "python -B -m pytest tests/test_x.py",
    "python -B -m pytest tests/test_x.py::test_name",
    "python -B -m pytest --durations=20 tests/test_x.py",
    "python -B -m pytest --durations 20 tests/test_x.py",
    "python -B -m pytest -k booking",
    "python -B -m pytest --lf",
    "python -B -m pytest -n 4 tests/test_a.py tests/test_b.py",
    "npx vitest run test/nuxt/helpDocs.test.ts",
    "npx vitest run test/unit",
    "npx vitest run tests/nuxt",
    "npx vitest run -t 'shows the title'",
    "npm test -- test/nuxt/x.test.ts",
    "npm run test:e2e -- test/e2e/x.spec.ts",
    "npx playwright test -g 'signs in'",
    "npx playwright test test/e2e/x.spec.ts",
    "echo 'run python -m pytest before a commit'",
    "grep -rn vitest package.json",
    "git commit -m 'npm test now faster'",
    "python -B -m pytest --version",
    "python -B -m pytest --collect-only -q",
    "npx playwright test --list",
    "curl -d \"note: ran npm test\" http://x",
    "gh pr create --body \"Ran npm test\"",
    "bash -c \"cd gui && npx vitest run test/unit\"",
    "npm run build",
    "npm run lint",
    "ruff check",
]


def check_matching() -> list[str]:
    failures = []
    for command in BLOCKED:
        if not scoped_tests.runs_full_suite(command):
            failures.append(f"not blocked: {command}")
    for command in ALLOWED:
        if scoped_tests.runs_full_suite(command):
            failures.append(f"blocked: {command}")
    return failures


def run_hook(command: str, project_dir: str) -> str:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": project_dir})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": project_dir}
    return subprocess.run([sys.executable, "-B", str(HOOK)], input=payload, capture_output=True, text=True,
                          env=env, check=True).stdout


def check_opt_in() -> list[str]:
    failures = []
    with tempfile.TemporaryDirectory() as plain, tempfile.TemporaryDirectory() as opted:
        skill = Path(opted, ".claude", "skills", "automated-tests")
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: automated-tests\n---\n")
        if run_hook("python -B -m pytest", plain):
            failures.append("denied in a project without a local automated-tests skill")
        out = run_hook("python -B -m pytest", opted)
        if '"permissionDecision": "deny"' not in out:
            failures.append(f"not denied in an opted-in project: {out!r}")
        if run_hook("python -B -m pytest tests/test_x.py", opted):
            failures.append("scoped run denied in an opted-in project")
    return failures


if __name__ == "__main__":
    problems = check_matching() + check_opt_in()
    for problem in problems:
        print(problem)
    print(f"{len(BLOCKED) + len(ALLOWED) + 3 - len(problems)} ok, {len(problems)} failed")
    sys.exit(1 if problems else 0)
