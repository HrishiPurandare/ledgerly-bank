"""Deterministic demo data: the same seed always produces the same customers, IBANs and statements.

Tests and demos depend on that: "Sara's current account balance is AED 18,240.15" must stay true.
"""

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction

from banking.iban import make_uae_iban
from banking.models import Account, Transaction

DEMO_PASSWORD = "NovaBank-Demo-2026"  # noqa: S105 - fictional demo customers only; see the DEBUG guard
DUBAI = ZoneInfo("Asia/Dubai")
CENT = Decimal("0.01")

T = Account.Type


@dataclass(frozen=True)
class DemoCustomer:
    email: str
    full_name: str
    accounts: tuple[tuple[str, str, str], ...]  # (type, nickname, status)


CUSTOMERS = (
    DemoCustomer(
        "sara@example.com",
        "Sara Khan",
        ((T.CURRENT, "Everyday", "ACTIVE"), (T.SAVINGS, "Rainy day", "ACTIVE")),
    ),
    DemoCustomer("omar@example.com", "Omar Ali", ((T.CURRENT, "Main", "ACTIVE"),)),
    DemoCustomer(
        "lina@example.com",
        "Lina Haddad",
        (
            (T.PREMIER, "Premier", "ACTIVE"),
            (T.SAVINGS, "School fees", "ACTIVE"),
            (T.CURRENT, "Old account", "FROZEN"),
        ),
    ),
)

MERCHANTS = [
    "Palm Grocers",
    "Marina Coffee House",
    "Oasis Fuel",
    "Souk Electronics",
    "Gulf Pharmacy",
    "Dune Cinemas",
    "Creek Bookshop",
    "Skyline Taxi",
]
BILLERS = ["Desert Power & Water", "Falcon Telecom", "Harbour Internet"]
EMPLOYERS = ["Atlas Logistics LLC", "Meridian Health FZ", "Corniche Consulting"]


def _money(rng: random.Random, low: int, high: int) -> Decimal:
    return (Decimal(rng.randint(low * 100, high * 100)) / 100).quantize(CENT)


def _at(day: date, rng: random.Random) -> datetime:
    return datetime.combine(day, time(rng.randint(7, 22), rng.randint(0, 59)), tzinfo=DUBAI)


def _events(account_type: str, rng: random.Random, start: date, today: date, employer: str):
    """Yield (day, direction, category, amount, description, counterparty) in date order."""
    D, C = Transaction.Direction, Transaction.Category
    opening = _money(rng, 2_000, 9_000) if account_type != T.PREMIER else _money(rng, 150_000, 220_000)
    yield start, D.CREDIT, C.TRANSFER_IN, opening, "Opening deposit", "Branch deposit"
    day = start + timedelta(days=1)
    while day <= today:
        if account_type in (T.CURRENT, T.PREMIER):
            if day.day == 25:
                pay = (
                    _money(rng, 14_000, 22_000) if account_type == T.CURRENT else _money(rng, 40_000, 55_000)
                )
                yield day, D.CREDIT, C.SALARY, pay, "Monthly salary", employer
            if day.day == 3:
                biller = rng.choice(BILLERS)
                yield day, D.DEBIT, C.BILL, _money(rng, 150, 900), f"Bill payment {biller}", biller
            for _ in range(rng.choice([0, 0, 1, 1, 2])):
                merchant = rng.choice(MERCHANTS)
                yield day, D.DEBIT, C.CARD, _money(rng, 12, 650), f"Card purchase {merchant}", merchant
            if rng.random() < 0.05:
                yield (
                    day,
                    D.DEBIT,
                    C.ATM,
                    Decimal(rng.choice([200, 500, 1000])),
                    "ATM withdrawal",
                    "NovaBank ATM",
                )
        else:  # savings
            if day.day == 26:
                yield day, D.CREDIT, C.TRANSFER_IN, _money(rng, 500, 2_500), "Monthly savings", "Own account"
            if day.day == 1:
                yield day, D.CREDIT, C.INTEREST, _money(rng, 5, 60), "Interest 3.25% p.a.", "NovaBank"
        day += timedelta(days=1)


@db_transaction.atomic
def seed(*, seed_value: int = 42, today: date | None = None, days: int = 90) -> dict:
    """Create the demo customers with ~90 days of statements. Returns a short summary."""
    rng = random.Random(seed_value)  # noqa: S311 - reproducible test data, not security
    today = today or date.today()
    start = today - timedelta(days=days)
    User = get_user_model()
    counter = 0
    summary = {"customers": 0, "accounts": 0, "transactions": 0}

    for customer in CUSTOMERS:
        user = User.objects.create_user(
            email=customer.email, full_name=customer.full_name, password=DEMO_PASSWORD
        )
        summary["customers"] += 1
        employer = rng.choice(EMPLOYERS)
        for account_type, nickname, status in customer.accounts:
            account_number = "".join(str(rng.randint(0, 9)) for _ in range(16))
            account = Account.objects.create(
                owner=user,
                iban=make_uae_iban(account_number),
                type=account_type,
                nickname=nickname,
                status=status,
                opened_at=_at(start, rng),
            )
            balance = Decimal("0.00")
            rows = []
            last_at = None
            for day, direction, category, amount, description, counterparty in _events(
                account_type, rng, start, today, employer
            ):
                signed = amount if direction == Transaction.Direction.CREDIT else -amount
                if balance + signed < 0:  # demo customers never go overdrawn
                    continue
                balance += signed
                counter += 1
                # Times must increase in the order balances were computed, or a statement sorted by time
                # shows a broken running balance (found by the running-balance test in test_seed.py).
                if last_at is not None and last_at.date() == day:
                    created_at = last_at + timedelta(minutes=rng.randint(5, 90))
                else:
                    created_at = datetime.combine(
                        day, time(rng.randint(7, 10), rng.randint(0, 59)), tzinfo=DUBAI
                    )
                last_at = created_at
                rows.append(
                    Transaction(
                        account=account,
                        direction=direction,
                        category=category,
                        amount=amount,
                        balance_after=balance,
                        description=description,
                        counterparty=counterparty,
                        reference=f"LDG{day:%y%m%d}{counter:06d}",
                        created_at=created_at,
                    )
                )
            Transaction.objects.bulk_create(rows)
            account.balance = balance
            account.save(update_fields=["balance"])
            summary["accounts"] += 1
            summary["transactions"] += len(rows)
    return summary


@db_transaction.atomic
def reset() -> None:
    """Remove the demo customers and everything they own (only theirs).

    Order matters: transfers protect their transactions and accounts, so they go first.
    """
    from django.db.models import Q

    from payments.models import Beneficiary, Transfer

    emails = [c.email for c in CUSTOMERS]
    Transfer.objects.filter(
        Q(owner__email__in=emails) | Q(to_account__owner__email__in=emails)  # incl. payments TO demo accounts
    ).delete()
    Beneficiary.objects.filter(owner__email__in=emails).delete()
    Transaction.objects.filter(account__owner__email__in=emails).delete()
    Account.objects.filter(owner__email__in=emails).delete()
    get_user_model().objects.filter(email__in=emails).delete()
