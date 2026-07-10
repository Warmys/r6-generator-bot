"""Backward-compatible premium-access helpers backed by SQLite."""

from utils import database as db


def has_active_premium(user_id):
    return db.has_active_premium(user_id)


def save_premium(data):
    for uid, expiry in data.items():
        db.premium_set(uid, expiry)


class _PremiumView(dict):
    """Dict-like live view over the premium table (kept for compatibility)."""

    def __getitem__(self, key):
        return db.premium_all()[str(key)]

    def __setitem__(self, key, value):
        db.premium_set(key, value)

    def __delitem__(self, key):
        db.premium_remove(key)

    def __contains__(self, key):
        return str(key) in db.premium_all()

    def items(self):
        return db.premium_all().items()

    def __iter__(self):
        return iter(db.premium_all())

    def __len__(self):
        return len(db.premium_all())


premium_users = _PremiumView()
