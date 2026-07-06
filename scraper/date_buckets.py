"""
date_buckets.py — Split a historical date range into scrape-sized windows
============================================================================
Twitter (`since:`/`until:`) and Google News RSS (`after:`/`before:`) both
return recency-biased results for a single wide-range query — asking for a
whole year back with one query mostly returns the last few days. Splitting
the range into several smaller sequential windows and querying each one
separately yields genuinely distributed historical coverage.
"""
from datetime import date, timedelta

MAX_BUCKETS = 12


def build_date_buckets(days_back: int, max_buckets: int = MAX_BUCKETS) -> list[tuple[str, str]]:
    """
    Split [today - days_back, today] into <= max_buckets (since, until) ISO-date
    windows, oldest first. Weekly buckets if that stays within max_buckets,
    otherwise monthly. days_back <= 7 returns a single bucket — matches the
    existing single-query behavior for the default/short-range case.
    """
    today = date.today()
    if days_back <= 7:
        return [((today - timedelta(days=days_back)).isoformat(), today.isoformat())]

    bucket_width = 7 if (days_back / 7) <= max_buckets else 30

    buckets: list[tuple[str, str]] = []
    until = today
    remaining = days_back
    while remaining > 0 and len(buckets) < max_buckets:
        width = min(bucket_width, remaining)
        since = until - timedelta(days=width)
        buckets.append((since.isoformat(), until.isoformat()))
        until = since
        remaining -= width

    buckets.reverse()  # oldest first
    return buckets
