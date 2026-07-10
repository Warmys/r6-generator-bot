"""Backward-compatible inventory helpers backed by SQLite."""

from utils import database as db


def get_account(path):
    """Legacy signature: pop one credential. `path` like 'data/free.txt'."""
    tier = "premium" if "premium" in path else "free"
    return db.stock_pop(tier)


def count_accounts(path):
    tier = "premium" if "premium" in path else "free"
    return db.stock_count(tier)
