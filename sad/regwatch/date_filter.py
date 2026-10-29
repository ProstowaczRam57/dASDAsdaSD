from datetime import datetime
from datetime import timedelta


class DateFilter:

    @staticmethod
    def is_recent(
        publication_date,
        lookback_days
    ):

        if publication_date is None:
            return True

        cutoff = (
            datetime.now()
            - timedelta(
                days=lookback_days
            )
        )

        return publication_date >= cutoff