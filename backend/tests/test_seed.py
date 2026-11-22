"""The demo data is test data: it must be reproducible, internally consistent and never reach production."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command
from django.db.models import Sum

from banking.iban import is_valid_uae_iban
from banking.models import Account, Transaction
from banking.seed import CUSTOMERS, DEMO_PASSWORD, reset, seed

TODAY = date(2026, 11, 22)


def snapshot():
    return sorted(
        (a.owner.email, a.iban, str(a.balance), a.transactions.count()) for a in Account.objects.all()
    )


def test_same_seed_same_data(db):
    seed(seed_value=7, today=TODAY)
    first = snapshot()
    reset()
    seed(seed_value=7, today=TODAY)
    assert snapshot() == first


def test_a_different_seed_gives_different_data(db):
    seed(seed_value=7, today=TODAY)
    first = snapshot()
    reset()
    seed(seed_value=8, today=TODAY)
    assert snapshot() != first


@pytest.fixture
def seeded(db):
    return seed(today=TODAY)


def test_every_balance_equals_the_sum_of_its_transactions(seeded):
    for account in Account.objects.all():
        credits = account.transactions.filter(direction="CREDIT").aggregate(s=Sum("amount"))["s"] or 0
        debits = account.transactions.filter(direction="DEBIT").aggregate(s=Sum("amount"))["s"] or 0
        assert account.balance == credits - debits, account.iban


def test_balance_after_is_a_consistent_running_balance_and_never_negative(seeded):
    for account in Account.objects.all():
        running = Decimal("0")
        for tx in account.transactions.order_by("created_at", "id"):
            running += tx.signed_amount
            assert tx.balance_after == running, tx.reference
            assert running >= 0
        assert running == account.balance


def test_seeded_data_looks_like_a_real_bank(seeded):
    assert seeded["customers"] == len(CUSTOMERS)
    assert all(is_valid_uae_iban(a.iban) for a in Account.objects.all())
    assert Account.objects.filter(status="FROZEN").count() == 1  # a UI state worth testing
    assert Transaction.objects.filter(category="SALARY").exists()
    assert not Transaction.objects.filter(created_at__date__gt=TODAY).exists()  # nothing in the future


def test_demo_customers_can_log_in(api, seeded):
    response = api.post(
        "/api/auth/login/", {"email": "sara@example.com", "password": DEMO_PASSWORD}, format="json"
    )
    assert response.status_code == 200


def test_seed_command_refuses_to_run_in_production(db, settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.delenv("LEDGERLY_ALLOW_SEED", raising=False)
    with pytest.raises(CommandError, match="Refusing"):
        call_command("seed")
    assert not Account.objects.exists()


def test_seed_command_refuses_to_duplicate_and_resets_on_request(db, settings):
    settings.DEBUG = True
    call_command("seed", "--today", "2026-11-22")
    with pytest.raises(CommandError, match="already exist"):
        call_command("seed")
    call_command("seed", "--reset", "--today", "2026-11-22")
    assert Account.objects.count() == sum(len(c.accounts) for c in CUSTOMERS)


def test_reset_only_removes_demo_customers(db, settings, make_user, make_account):
    settings.DEBUG = True
    real = make_account(make_user(email="real.customer@example.com"), balance="10.00")
    call_command("seed", "--today", "2026-11-22")
    call_command("seed", "--reset", "--today", "2026-11-22")
    assert Account.objects.filter(pk=real.pk).exists()
