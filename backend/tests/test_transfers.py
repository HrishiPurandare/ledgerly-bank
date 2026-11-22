"""Transfers: every rule at its exact boundary, and proof that a rejected transfer leaves no trace."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from banking.models import Account, Transaction
from payments.models import Beneficiary, Transfer
from tests.conftest import PASSWORD

URL = "/api/transfers/"
EXTERNAL_IBAN = "AE070331234567890123456"  # another UAE bank
DUBAI = ZoneInfo("Asia/Dubai")


@pytest.fixture
def current(make_account, user):
    return make_account(user, balance="80000.00", nickname="Everyday")


@pytest.fixture
def savings(make_account, user):
    return make_account(user, type="SAVINGS", balance="5000.00")


@pytest.fixture
def omar(make_user):
    return make_user(email="omar@example.com", full_name="Omar Ali")


@pytest.fixture
def omar_account(make_account, omar):
    return make_account(omar, balance="100.00")


@pytest.fixture
def make_beneficiary(user):
    def make(iban=EXTERNAL_IBAN, name="Fatima Noor", hours_ago=48, status="ACTIVE"):
        activated = timezone.now() - timedelta(hours=hours_ago) if status == "ACTIVE" else None
        return Beneficiary.objects.create(
            owner=user, name=name, iban=iban, status=status, activated_at=activated
        )

    return make


def send(api, key=None, **body):
    return api.post(URL, body, format="json", HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))


def code(response) -> str:
    return response.json().get("code")


def balance(account) -> Decimal:
    account.refresh_from_db()
    return account.balance


# ---------- the three kinds of transfer ----------


def test_own_account_transfer_moves_money_instantly(auth_api, current, savings):
    response = send(auth_api, from_account=current.id, to_account=savings.id, amount="250.50")
    assert response.status_code == 201, response.content
    assert response.json()["kind"] == "OWN" and response.json()["status"] == "COMPLETED"
    assert balance(current) == Decimal("79749.50") and balance(savings) == Decimal("5250.50")
    assert savings.transactions.get().balance_after == Decimal("5250.50")


def test_transfer_to_another_ledgerly_customer_is_instant(auth_api, current, omar_account, make_beneficiary):
    beneficiary = make_beneficiary(iban=omar_account.iban, name="Omar Ali")
    response = send(
        auth_api, from_account=current.id, beneficiary=beneficiary.id, amount="1000.00", remarks="Rent"
    )
    assert response.json()["kind"] == "INTERNAL" and response.json()["status"] == "COMPLETED"
    assert balance(omar_account) == Decimal("1100.00")
    credit = omar_account.transactions.get()
    assert credit.counterparty == "Sara Khan" and "Rent" in credit.description


def test_transfer_to_another_bank_is_pending_and_only_debits(auth_api, current, make_beneficiary):
    response = send(auth_api, from_account=current.id, beneficiary=make_beneficiary().id, amount="300.00")
    body = response.json()
    assert body["kind"] == "LOCAL" and body["status"] == "PENDING"
    assert uuid.UUID(body["uetr"]).version == 4  # the end-to-end id a pacs.008 message carries
    assert balance(current) == Decimal("79700.00")
    assert Transaction.objects.count() == 1


# ---------- money rules ----------


def test_sending_the_exact_balance_is_allowed(auth_api, savings, current):
    assert send(auth_api, from_account=savings.id, to_account=current.id, amount="5000.00").status_code == 201
    assert balance(savings) == Decimal("0.00")


def test_one_fils_more_than_the_balance_is_refused_and_nothing_changes(auth_api, savings, current):
    response = send(auth_api, from_account=savings.id, to_account=current.id, amount="5000.01")
    assert response.status_code == 400 and code(response) == "insufficient_funds"
    assert balance(savings) == Decimal("5000.00") and balance(current) == Decimal("80000.00")
    assert not Transaction.objects.exists() and not Transfer.objects.exists()


@pytest.mark.parametrize("amount", ["0", "0.00", "-5", "10.001", "abc", None])
def test_invalid_amounts_are_rejected(auth_api, current, savings, amount):
    body = {"from_account": current.id, "to_account": savings.id}
    if amount is not None:
        body["amount"] = amount
    assert send(auth_api, **body).status_code == 400


def test_exactly_one_destination_is_required(auth_api, current, savings, make_beneficiary):
    both = send(
        auth_api,
        from_account=current.id,
        to_account=savings.id,
        beneficiary=make_beneficiary().id,
        amount="1",
    )
    neither = send(auth_api, from_account=current.id, amount="1")
    assert both.status_code == neither.status_code == 400


def test_same_account_is_refused(auth_api, current):
    assert code(send(auth_api, from_account=current.id, to_account=current.id, amount="1")) == "same_account"


def test_a_frozen_account_cannot_send(auth_api, current, savings):
    Account.objects.filter(pk=current.pk).update(status="FROZEN")
    assert (
        code(send(auth_api, from_account=current.id, to_account=savings.id, amount="1")) == "account_frozen"
    )


def test_a_frozen_account_cannot_receive(auth_api, current, omar_account, make_beneficiary):
    Account.objects.filter(pk=omar_account.pk).update(status="FROZEN")
    beneficiary = make_beneficiary(iban=omar_account.iban)
    response = send(auth_api, from_account=current.id, beneficiary=beneficiary.id, amount="1")
    assert code(response) == "destination_unavailable"


def test_a_pending_beneficiary_cannot_be_paid(auth_api, current, make_beneficiary):
    beneficiary = make_beneficiary(status="PENDING")
    response = send(auth_api, from_account=current.id, beneficiary=beneficiary.id, amount="1")
    assert code(response) == "beneficiary_not_active"


def test_other_customers_accounts_and_beneficiaries_are_404(auth_api, current, omar, omar_account):
    theirs = Beneficiary.objects.create(owner=omar, name="X", iban=EXTERNAL_IBAN, status="ACTIVE")
    from_theirs = send(auth_api, from_account=omar_account.id, to_account=current.id, amount="1")
    to_theirs = send(auth_api, from_account=current.id, to_account=omar_account.id, amount="1")
    via_theirs = send(auth_api, from_account=current.id, beneficiary=theirs.id, amount="1")
    assert from_theirs.status_code == to_theirs.status_code == via_theirs.status_code == 404
    assert balance(omar_account) == Decimal("100.00")


# ---------- daily limit: AED 50,000 per customer per Dubai day, across all accounts ----------


def test_exactly_the_daily_limit_is_allowed_then_one_fils_more_is_not(auth_api, current, make_beneficiary):
    beneficiary = make_beneficiary()
    assert (
        send(auth_api, from_account=current.id, beneficiary=beneficiary.id, amount="50000.00").status_code
        == 201
    )
    response = send(auth_api, from_account=current.id, beneficiary=beneficiary.id, amount="0.01")
    assert code(response) == "daily_limit_exceeded" and "AED 0.00 more" in response.json()["detail"]


def test_the_daily_limit_spans_all_accounts(auth_api, current, savings, make_beneficiary):
    beneficiary = make_beneficiary()
    send(auth_api, from_account=current.id, beneficiary=beneficiary.id, amount="46000.00")
    response = send(auth_api, from_account=savings.id, beneficiary=beneficiary.id, amount="4000.01")
    assert code(response) == "daily_limit_exceeded"


def test_moving_money_between_own_accounts_does_not_use_the_limit(
    auth_api, current, savings, make_beneficiary
):
    send(auth_api, from_account=current.id, to_account=savings.id, amount="60000.00")
    beneficiary = make_beneficiary()
    assert (
        send(auth_api, from_account=savings.id, beneficiary=beneficiary.id, amount="50000.00").status_code
        == 201
    )


def test_yesterday_in_dubai_does_not_count_even_if_it_is_today_in_utc(user, current, make_beneficiary):
    from payments import rules

    beneficiary = make_beneficiary()
    now = datetime(2026, 11, 22, 1, 30, tzinfo=DUBAI)  # 21:30 UTC on the 21st
    late_yesterday = datetime(2026, 11, 21, 23, 59, tzinfo=DUBAI)  # same UTC date as `now`
    debit = Transaction.objects.create(
        account=current,
        direction="DEBIT",
        category="TRANSFER_OUT",
        amount=Decimal("40000"),
        balance_after=Decimal("0"),
        description="Old transfer",
        reference="OLD1D",
        created_at=late_yesterday,
    )
    Transfer.objects.create(
        owner=user,
        reference="OLD1",
        kind="LOCAL",
        status="PENDING",
        from_account=current,
        beneficiary=beneficiary,
        creditor_name="Fatima Noor",
        creditor_iban=EXTERNAL_IBAN,
        amount=Decimal("40000"),
        idempotency_key="k1",
        request_fingerprint="x",
        debit=debit,
        created_at=late_yesterday,
    )
    assert rules.sent_today(user, now) == Decimal("0")


# ---------- new beneficiary: AED 10,000 in the first 24 hours ----------


def test_new_beneficiary_allows_10000_in_total_then_refuses(auth_api, current, make_beneficiary):
    new = make_beneficiary(hours_ago=1)
    assert send(auth_api, from_account=current.id, beneficiary=new.id, amount="6000.00").status_code == 201
    assert send(auth_api, from_account=current.id, beneficiary=new.id, amount="4000.00").status_code == 201
    response = send(auth_api, from_account=current.id, beneficiary=new.id, amount="0.01")
    assert code(response) == "new_beneficiary_limit"


def test_new_beneficiary_limit_is_cumulative(auth_api, current, make_beneficiary):
    new = make_beneficiary(hours_ago=1)
    send(auth_api, from_account=current.id, beneficiary=new.id, amount="6000.00")
    response = send(auth_api, from_account=current.id, beneficiary=new.id, amount="4000.01")
    assert code(response) == "new_beneficiary_limit" and "AED 4000.00 more" in response.json()["detail"]


def test_after_24_hours_the_new_beneficiary_limit_no_longer_applies(auth_api, current, make_beneficiary):
    settled = make_beneficiary(hours_ago=24.01)
    assert (
        send(auth_api, from_account=current.id, beneficiary=settled.id, amount="15000.00").status_code == 201
    )


# ---------- idempotency ----------


def test_retrying_with_the_same_key_never_pays_twice(auth_api, current, savings):
    body = {"from_account": current.id, "to_account": savings.id, "amount": "100.00"}
    first = send(auth_api, key="retry-1", **body)
    again = send(auth_api, key="retry-1", **body)
    assert first.status_code == again.status_code == 201
    assert again.json() == first.json() and again["Idempotent-Replayed"] == "true"
    assert Transfer.objects.count() == 1 and balance(current) == Decimal("79900.00")


def test_reusing_a_key_for_a_different_transfer_is_a_conflict(auth_api, current, savings):
    send(auth_api, key="k", from_account=current.id, to_account=savings.id, amount="100.00")
    response = send(auth_api, key="k", from_account=current.id, to_account=savings.id, amount="999.00")
    assert response.status_code == 409 and code(response) == "idempotency_key_reused"


def test_the_idempotency_key_is_required(auth_api, current, savings):
    body = {"from_account": current.id, "to_account": savings.id, "amount": "1.00"}
    response = auth_api.post(URL, body, format="json")
    assert response.status_code == 400 and code(response) == "idempotency_key_required"


def test_idempotency_keys_are_per_customer(auth_api, api, current, savings, omar, make_account):
    send(auth_api, key="shared", from_account=current.id, to_account=savings.id, amount="1.00")
    omar_a, omar_b = make_account(omar, balance="10.00"), make_account(omar, balance="0.00")
    token = api.post("/api/auth/login/", {"email": omar.email, "password": PASSWORD}, format="json").json()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token['access']}")
    assert (
        send(api, key="shared", from_account=omar_a.id, to_account=omar_b.id, amount="2.00").status_code
        == 201
    )


# ---------- reading transfers ----------


def test_transfers_list_and_detail_are_owner_only(auth_api, current, savings, omar, make_account):
    mine = send(auth_api, from_account=current.id, to_account=savings.id, amount="1.00").json()
    assert [t["id"] for t in auth_api.get(URL).json()["results"]] == [mine["id"]]
    assert auth_api.get(f"{URL}{mine['id']}/").status_code == 200
    assert auth_api.get(f"{URL}{mine['id'] + 999}/").status_code == 404
