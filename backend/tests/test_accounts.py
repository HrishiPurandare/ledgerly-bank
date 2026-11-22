"""Accounts and statements. The core rule: a customer only ever sees their own money."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import PASSWORD

DUBAI = ZoneInfo("Asia/Dubai")


@pytest.fixture
def other(make_user):
    return make_user(email="intruder@example.com", full_name="Ivan Intruder")


@pytest.fixture
def sara_account(make_account, user):
    return make_account(user, balance="1000.00", nickname="Everyday")


@pytest.fixture
def other_account(make_account, other):
    return make_account(other, balance="99999.00")


def test_account_list_shows_only_my_accounts(auth_api, sara_account, other_account):
    response = auth_api.get("/api/accounts/")
    assert response.status_code == 200
    assert [a["id"] for a in response.json()["results"]] == [sara_account.id]


def test_account_shape_money_as_a_string_and_a_readable_iban(auth_api, sara_account):
    data = auth_api.get(f"/api/accounts/{sara_account.id}/").json()
    assert data["balance"] == "1000.00"  # a string: JSON numbers would lose cents as floats
    assert data["iban_display"].replace(" ", "") == data["iban"]
    assert data["type_label"] == "Everyday Current Account"


# ---------- broken object-level authorization (IDOR), OWASP API #1 ----------


def test_someone_elses_account_is_404_not_403(auth_api, other_account):
    assert auth_api.get(f"/api/accounts/{other_account.id}/").status_code == 404


def test_someone_elses_statement_is_404(auth_api, other_account, add_tx):
    add_tx(other_account, "50.00")
    assert auth_api.get(f"/api/accounts/{other_account.id}/transactions/").status_code == 404


def test_a_missing_account_and_someone_elses_look_identical(auth_api, other_account):
    theirs = auth_api.get(f"/api/accounts/{other_account.id}/")
    missing = auth_api.get("/api/accounts/987654/")
    # Same status and body: probing ids reveals nothing about which accounts exist.
    assert (theirs.status_code, theirs.json()) == (missing.status_code, missing.json())


def test_the_owner_of_the_other_account_can_see_it(api, other_account):
    token = api.post(
        "/api/auth/login/", {"email": "intruder@example.com", "password": PASSWORD}, format="json"
    )
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.json()['access']}")
    assert api.get(f"/api/accounts/{other_account.id}/").status_code == 200  # the 404 above wasn't a bug


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_accounts_are_read_only_through_the_api(auth_api, sara_account, method):
    url = f"/api/accounts/{sara_account.id}/"
    assert getattr(auth_api, method)(url, {"balance": "1000000.00"}, format="json").status_code == 405
    sara_account.refresh_from_db()
    assert str(sara_account.balance) == "1000.00"


# ---------- statements ----------


@pytest.fixture
def statement(sara_account, add_tx):
    """Five transactions on known days, oldest first."""
    day = datetime(2026, 11, 1, 10, 0, tzinfo=DUBAI)
    return [
        add_tx(
            sara_account, "15000.00", "CREDIT", "SALARY", "Monthly salary", when=day, counterparty="Atlas"
        ),
        add_tx(
            sara_account, "45.50", when=day + timedelta(days=1), description="Card purchase Marina Coffee"
        ),
        add_tx(
            sara_account, "420.00", category="BILL", when=day + timedelta(days=2), description="Bill Falcon"
        ),
        add_tx(
            sara_account, "500.00", category="ATM", when=day + timedelta(days=5), description="ATM withdrawal"
        ),
        add_tx(sara_account, "12.75", when=day + timedelta(days=9), description="Card purchase Palm Grocers"),
    ]


def statement_of(api, account, query=""):
    response = api.get(f"/api/accounts/{account.id}/transactions/{query}")
    assert response.status_code == 200, response.content
    return response.json()


def test_statement_is_newest_first(auth_api, sara_account, statement):
    refs = [t["reference"] for t in statement_of(auth_api, sara_account)["results"]]
    assert refs == [t.reference for t in reversed(statement)]


def test_balance_after_is_a_running_balance(auth_api, sara_account, statement):
    rows = statement_of(auth_api, sara_account)["results"]
    assert rows[0]["balance_after"] == "15021.75"  # 1000 + 15000 - 45.50 - 420 - 500 - 12.75
    assert rows[-1]["balance_after"] == "16000.00"


@pytest.mark.parametrize(
    ("query", "expected_count"),
    [
        ("?direction=CREDIT", 1),
        ("?direction=DEBIT", 4),
        ("?category=CARD", 2),
        ("?date_from=2026-11-03&date_to=2026-11-06", 2),  # inclusive on both ends
        ("?min_amount=420", 3),
        ("?max_amount=45.50", 2),
        ("?search=coffee", 1),  # case-insensitive
        ("?search=atlas", 1),  # matches the counterparty too
        ("?direction=DEBIT&category=CARD&min_amount=20", 1),
    ],
)
def test_statement_filters(auth_api, sara_account, statement, query, expected_count):
    assert statement_of(auth_api, sara_account, query)["count"] == expected_count


@pytest.mark.parametrize("query", ["?direction=SIDEWAYS", "?date_from=yesterday", "?min_amount=lots"])
def test_invalid_filters_are_a_400_not_an_empty_list(auth_api, sara_account, statement, query):
    response = auth_api.get(f"/api/accounts/{sara_account.id}/transactions/{query}")
    assert response.status_code == 400


def test_statement_is_paginated(auth_api, sara_account, add_tx):
    for _ in range(25):
        add_tx(sara_account, "1.00", "CREDIT", "TRANSFER_IN")
    first = statement_of(auth_api, sara_account)
    assert first["count"] == 25 and len(first["results"]) == 20 and first["next"]
    second = statement_of(auth_api, sara_account, "?page=2")
    assert len(second["results"]) == 5 and second["next"] is None
