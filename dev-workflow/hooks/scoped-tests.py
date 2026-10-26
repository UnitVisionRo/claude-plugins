#!/usr/bin/env python3
"""PreToolUse/Bash hook: refuse an unscoped run of a project's full test suites.

Rule (the `dev-workflow:automated-tests` skill): while iterating on a change, run only the tests that cover it --
the affected pytest module(s), Vitest file(s), Playwright spec(s). The full suites run once, right before a commit
the user ordered, and that run is marked by prefixing the command with `FULL_SUITE=1`.

Opt-in per project: the hook acts only where `.claude/skills/automated-tests/SKILL.md` exists in the project, the
local skill that supplies the project's test facts. Everywhere else it does nothing.

Refused, unless the command contains `FULL_SUITE=1`:
- pytest (`pytest`, `python -m pytest`, `uv run pytest`, ...) with no test path, node id, `-k` or `--lf`;
- Vitest: `npm test` / `npm run test` / `vitest run` / `npx vitest` with no test file or `-t` filter;
- Playwright: `npm run test:e2e` / `playwright test` with no spec file or `-g` filter.

Matching strategy (as ~/.claude/hooks/block-ruff-format.py): split the command on shell separators and look at
each segment; segments starting with a text command (echo, grep, ...) are skipped, so talking about the suites
still works. A scope is any later argument that is not an option and not a whole test root (`tests/`, `.`).
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

# Commands whose arguments are text to display or search, not a program to run.
TEXT_COMMANDS = frozenset(
    {"#", "ack", "ag", "awk", "bat", "cat", "diff", "echo", "egrep", "fgrep", "git", "grep", "head", "less", "more",
     "printf", "rg", "sed", "tail"}
)

# Shell separators that begin a new command position.
SEPARATORS = re.compile(r"(?:\|\||&&|[;|&\n()])")

# Redirections (`2>&1`, `> out.log`, `< in`), removed first: their targets are not test scopes
REDIRECTIONS = re.compile(r"\d*(?:>&\d+|>>?\s*\S+|<\s*\S+)")

# Options that select tests by name or by last result: a scope as good as a file
NAME_FILTERS = {
    "pytest": ("-k", "--lf", "--last-failed", "--sw", "--stepwise"),
    "vitest": ("-t", "--testNamePattern", "--changed"),
    "playwright": ("-g", "--grep", "--last-failed"),
}

# Options that take a value, whose value is not a scope (e.g. `-n 4`, `--reporter dot`)
VALUE_OPTIONS = {"-n", "-p", "-c", "-m", "--reporter", "--project", "--workers", "-j", "--config", "--maxfail",
                 "--sequence.seed", "--rootdir", "--durations"}

# npm options before the script name that take a value (`npm --prefix gui test`)
NPM_VALUE_OPTIONS = {"--prefix", "-C", "--workspace", "-w"}

# Options with which the command runs no tests
NOT_RUNNING = {"--version", "-V", "-h", "--help", "--co", "--collect-only", "--list"}

# A whole test root is the full suite, not a scope
TEST_ROOTS = {".", "test", "tests"}

# Shells whose `-c` argument is a command line of its own (`-c`, `-lc`, `-ec`, ...)
SHELLS = {"sh", "bash", "zsh", "dash"}
SHELL_C_FLAG = re.compile(r"-[a-zA-Z]*c[a-zA-Z]*")

LOCAL_SKILL = Path(".claude", "skills", "automated-tests", "SKILL.md")

REASON = (
    "BLOCKED by project rule: run only the tests that cover your change while iterating -- e.g. "
    "`python -B -m pytest tests/test_x.py`, `npx vitest run <test file>`, `npm run test:e2e -- <spec>`. "
    "Shared code justifies a wider targeted run, not an unscoped one. The full suites run once, right before a "
    "commit the user ordered: then prefix the command with `FULL_SUITE=1`. Rule: `dev-workflow:automated-tests`; "
    "this project's test commands: `.claude/skills/automated-tests/SKILL.md`."
)


def _npm_script(args: list[str]) -> list[str]:
    """npm's arguments with the options before the script name removed."""
    skip = False
    for i, arg in enumerate(args):
        if skip:
            skip = False
        elif arg in NPM_VALUE_OPTIONS:
            skip = True
        elif not arg.startswith("-"):
            return args[i:]
    return []


def _suite(words: list[str]) -> tuple[str, list[str]] | None:
    """The suite a segment runs and the arguments after it, or None."""
    for i, word in enumerate(words):
        name = word.rsplit("/", 1)[-1]
        if name == "pytest" or (name == "-m" and i + 1 < len(words) and words[i + 1] == "pytest"):
            start = i + 2 if name == "-m" else i + 1
            return "pytest", words[start:]
        if name == "vitest":
            rest = words[i + 1:]
            return "vitest", rest[1:] if rest[:1] == ["run"] else rest
        if name == "playwright" and words[i + 1:i + 2] == ["test"]:
            return "playwright", words[i + 2:]
        if name == "npm":
            rest = _npm_script(words[i + 1:])
            if rest[:1] == ["test"]:
                return "vitest", rest[1:]
            if rest[:2] == ["run", "test"]:
                return "vitest", rest[2:]
            if rest[:2] == ["run", "test:e2e"]:
                return "playwright", rest[2:]
            return None
    return None


def _scoped(suite: str, args: list[str]) -> bool:
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg == "--":
            continue
        if arg.split("=", 1)[0] in NAME_FILTERS[suite] or arg in NOT_RUNNING:
            return True
        if arg in VALUE_OPTIONS:
            skip = True
            continue
        if not arg.startswith("-") and arg.rstrip("/").rsplit("/", 1)[-1] not in TEST_ROOTS | {""}:
            return True
    return False


def _shell_c_commands(command: str) -> list[str]:
    """The inner commands of `sh -c '...'`, `bash -lc "..."`: tokenized on the whole command, so the separators
    inside the quotes stay inside them."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    inner = []
    for i, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] not in SHELLS:
            continue
        for j in range(i + 1, len(tokens) - 1):
            if not SHELL_C_FLAG.fullmatch(tokens[j]):
                if not tokens[j].startswith("-"):
                    break
                continue
            inner.append(tokens[j + 1])
            break
    return inner


def runs_full_suite(command: str) -> bool:
    if "FULL_SUITE=1" in command:
        return False
    if any(runs_full_suite(inner) for inner in _shell_c_commands(command)):
        return True
    for segment in SEPARATORS.split(REDIRECTIONS.sub(" ", command)):
        try:
            words = shlex.split(segment)
        except ValueError:
            words = segment.split()
        # leading VAR=value assignments
        while words and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
            words = words[1:]
        if not words or words[0].lstrip("\"'") in TEXT_COMMANDS:
            continue
        found = _suite(words)
        if found and not _scoped(*found):
            return True
    return False


def opted_in(payload: dict) -> bool:
    project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ""
    return bool(project) and (Path(project) / LOCAL_SKILL).is_file()


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not opted_in(payload) or not runs_full_suite(command):
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
