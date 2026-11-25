"""Transfer limits from NovaBank's published policy (the text the NovaAsk chatbot answers from):

- "The default daily limit ... is AED 50,000 per customer, across all accounts."
- "Transfers to a newly added beneficiary are limited to AED 10,000 during the first 24 hours."
- "Customers can add up to 100 beneficiaries."

Pure functions over a `now` argument, so every boundary can be tested without waiting or mocking the clock.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Sum

DUBAI = ZoneInfo("Asia/Dubai")


def daily_limit() -> Decimal:
    return Decimal(settings.NOVABANK["DAILY_LIMIT"])


def new_beneficiary_limit() -> Decimal:
    return Decimal(settings.NOVABANK["NEW_BENEFICIARY_LIMIT"])


def start_of_day(now: datetime) -> datetime:
    """Midnight in Dubai: a customer's "day" is their local day, not UTC's."""
    local = now.astimezone(DUBAI)
    return datetime.combine(local.date(), time.min, tzinfo=DUBAI)


def sent_today(user, now: datetime) -> Decimal:
    """Total sent to other people today. Moving money between your own accounts doesn't count."""
    from payments.models import Transfer

    total = (
        # No upper bound on purpose: `now` is read before the customer lock is taken, so a transfer that
        # won the race for the lock can be stamped a moment AFTER this `now`. It still counts.
        # (Found by test_two_accounts_cannot_both_slip_under_the_daily_limit on Postgres.)
        Transfer.objects.filter(owner=user, created_at__gte=start_of_day(now))
        .exclude(kind=Transfer.Kind.OWN)
        .aggregate(total=Sum("amount"))["total"]
    )
    return total or Decimal("0")


def in_cooling_off(beneficiary, now: datetime) -> bool:
    hours = settings.NOVABANK["NEW_BENEFICIARY_HOURS"]
    return beneficiary.activated_at is not None and now < beneficiary.activated_at + timedelta(hours=hours)


def sent_to_new_beneficiary(beneficiary) -> Decimal:
    from payments.models import Transfer

    total = Transfer.objects.filter(
        beneficiary=beneficiary, created_at__gte=beneficiary.activated_at
    ).aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")
