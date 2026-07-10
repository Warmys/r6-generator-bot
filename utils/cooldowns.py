"""Backward-compatible cooldown helpers backed by SQLite."""

from utils import database as db


def get_cooldown_seconds(user_id, tier):
    return db.get_cooldown_seconds(user_id, tier)


def check_cooldown(user_id, tier):
    return db.check_cooldown(user_id, tier)


def update_cooldown(user_id, tier):
    db.update_cooldown(user_id, tier)


def set_custom_cooldown(user_id, tier, seconds):
    db.set_custom_cooldown(user_id, tier, seconds)
