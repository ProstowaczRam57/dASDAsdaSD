from datetime import date, datetime, timedelta, timezone
from typing import Optional


def to_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    Naive datetimes are assumed to be UTC; dates are treated as midnight UTC.
    This keeps comparisons safe when sources mix ``Z`` timestamps with plain
    ``YYYY-MM-DD`` values.
    """

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime(
            value.year,
            value.month,
            value.day,
            tzinfo=timezone.utc,
        )

    raise TypeError(f"Expected date or datetime, got {type(value)!r}")


class DateFilter:
    """Decides whether a publication falls inside the lookback window."""

    def __init__(self, lookback_days: int, now: Optional[datetime] = None):
        if lookback_days < 0:
            raise ValueError("lookback_days must be >= 0")

        self.lookback_days = lookback_days
        self.now = to_utc(now) if now is not None else datetime.now(timezone.utc)

    @property
    def cutoff(self) -> datetime:
        return self.now - timedelta(days=self.lookback_days)

    def is_recent(self, publication_date: Optional[datetime]) -> bool:
        # Unknown dates are kept: some sources never expose a date and
        # dropping them would silently lose publications.
        if publication_date is None:
            return True

        return to_utc(publication_date) >= self.cutoff
