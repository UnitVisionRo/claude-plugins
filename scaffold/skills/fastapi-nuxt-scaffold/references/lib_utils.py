from datetime import UTC, datetime


def utcnow() -> datetime:
    """The only way this app gets "now": aware UTC (root CLAUDE.md)."""
    return datetime.now(UTC)
