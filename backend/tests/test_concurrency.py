"""Race conditions: many requests at the same moment. Postgres only, because SQLite ignores row locks.

These run in CI's Postgres job. Each thread gets its own database connection, like separate web workers.
"""

import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection, connections
from django.utils import timezone

from payments import services
from payments.errors import TransferRejected
from payments.models import Beneficiary, Transfer

pytestmark = [
    pytest.mark.django_db(transaction=True),  # real commits, so other connections can see them
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs real row locks (Postgres)"),
]


def run_together(calls):
    """Start every call at the same instant; return each one's result or error code."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def worker(i, call):
        try:
            barrier.wait()
            results[i] = ("ok", call())
        except TransferRejected as exc:
            results[i] = ("rejected", exc.detail["code"])
        finally:
            connections.close_all()  # each thread's own connection

    threads = [threading.Thread(target=worker, args=(i, c)) for i, c in enumerate(calls)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def transfer(user, key, **data):
    return lambda: services.create_transfer(user, data, idempotency_key=key, now=timezone.now())


def test_ten_simultaneous_withdrawals_never_overdraw(user, make_account):
    source = make_account(user, balance="5000.00")
    target = make_account(user, balance="0.00")
    calls = [
        transfer(user, f"k{i}", from_account=source.id, to_account=target.id, amount=Decimal("1000.00"))
        for i in range(10)
    ]
    results = run_together(calls)
    assert sum(r[0] == "ok" for r in results) == 5
    assert sorted(r[1] for r in results if r[0] == "rejected") == ["insufficient_funds"] * 5
    source.refresh_from_db()
    target.refresh_from_db()
    assert source.balance == Decimal("0.00") and target.balance == Decimal("5000.00")


def test_two_accounts_cannot_both_slip_under_the_daily_limit(user, make_account):
    first, second = make_account(user, balance="40000.00"), make_account(user, balance="40000.00")
    payee = Beneficiary.objects.create(
        owner=user,
        name="Fatima Noor",
        iban="AE070331234567890123456",
        status="ACTIVE",
        activated_at=timezone.now() - timedelta(days=3),
    )
    results = run_together(
        [
            transfer(user, "a", from_account=first.id, beneficiary=payee.id, amount=Decimal("30000.00")),
            transfer(user, "b", from_account=second.id, beneficiary=payee.id, amount=Decimal("30000.00")),
        ]
    )
    # Without the per-customer lock both would see "AED 0 sent today" and pass: AED 60,000 in one day.
    assert sorted(r[0] for r in results) == ["ok", "rejected"]
    assert [r[1] for r in results if r[0] == "rejected"] == ["daily_limit_exceeded"]


def test_the_same_request_sent_five_times_at_once_pays_once(user, make_account):
    source = make_account(user, balance="1000.00")
    target = make_account(user, balance="0.00")
    calls = [
        transfer(user, "double-click", from_account=source.id, to_account=target.id, amount=Decimal("100.00"))
        for _ in range(5)
    ]
    results = run_together(calls)
    assert all(r[0] == "ok" for r in results)
    assert len({r[1][0].pk for r in results}) == 1  # everyone got the same transfer back
    assert Transfer.objects.count() == 1
    source.refresh_from_db()
    assert source.balance == Decimal("900.00")
