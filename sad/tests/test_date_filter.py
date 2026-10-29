from datetime import datetime, timedelta, timezone

import pytest
from regwatch.date_filter import DateFilter, to_utc


def test_naive_and_aware_dates_are_comparable():
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    date_filter = DateFilter(30, now=now)

    assert date_filter.is_recent(datetime(2026, 10, 20, 10, 0))
    assert date_filter.is_recent(datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc))


def test_old_publication_is_rejected():
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    date_filter = DateFilter(30, now=now)

    assert not date_filter.is_recent(now - timedelta(days=31))
    assert date_filter.is_recent(now - timedelta(days=29))


def test_missing_date_is_kept():
    date_filter = DateFilter(30, now=datetime(2026, 10, 29, tzinfo=timezone.utc))

    assert date_filter.is_recent(None)


def test_timezone_is_normalized_to_utc():
    value = datetime(2026, 10, 29, 14, 0, tzinfo=timezone(timedelta(hours=2)))

    normalized = to_utc(value)

    assert normalized.hour == 12
    assert normalized.tzinfo == timezone.utc


def test_negative_lookback_is_rejected():
    with pytest.raises(ValueError):
        DateFilter(-1)
