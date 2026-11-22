"""Authentication: register, login, refresh, profile. Each rule is tested both ways: holds, and rejects."""

from datetime import timedelta

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from tests.conftest import PASSWORD

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
ME = "/api/auth/me/"


def login(api, email="sara@example.com", password=PASSWORD):
    return api.post(LOGIN, {"email": email, "password": password}, format="json")


# ---------- register ----------


def test_register_creates_a_customer_and_never_returns_the_password(api, db, django_user_model):
    body = {"email": "Omar@Example.com", "full_name": "Omar Ali", "password": PASSWORD}
    response = api.post(REGISTER, body, format="json")
    assert response.status_code == 201
    assert response.json().keys() == {"id", "email", "full_name", "date_joined"}
    assert response.json()["email"] == "omar@example.com"  # stored lower-case
    stored = django_user_model.objects.get(email="omar@example.com")
    assert stored.password != PASSWORD and stored.check_password(PASSWORD)  # hashed


def test_register_rejects_a_duplicate_email_whatever_its_case(api, user):
    body = {"email": "SARA@example.com", "full_name": "Someone Else", "password": PASSWORD}
    response = api.post(REGISTER, body, format="json")
    assert response.status_code == 400
    assert "email" in response.json()


@pytest.mark.parametrize(
    "password",
    ["Short1!", "password1234", "1234567890123", "omar.ali.example"],
    ids=["too-short", "common", "all-digits", "similar-to-email"],
)
def test_register_enforces_password_rules(api, db, password):
    body = {"email": "omar.ali@example.com", "full_name": "Omar Ali", "password": password}
    response = api.post(REGISTER, body, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("missing", ["email", "full_name", "password"])
def test_register_requires_every_field(api, db, missing):
    body = {"email": "omar@example.com", "full_name": "Omar Ali", "password": PASSWORD}
    body.pop(missing)
    assert api.post(REGISTER, body, format="json").status_code == 400


# ---------- login ----------


def test_login_returns_an_access_and_a_refresh_token(api, user):
    response = login(api)
    assert response.status_code == 200
    assert {"access", "refresh"} <= response.json().keys()


def test_login_failure_looks_the_same_for_a_wrong_password_and_an_unknown_email(api, user):
    wrong_password = login(api, password="Not-The-Password-1")
    unknown_email = login(api, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    # Same message, so an attacker can't use login to find out which emails are customers.
    assert wrong_password.json() == unknown_email.json()


def test_a_deactivated_customer_cannot_log_in(api, make_user):
    make_user(email="gone@example.com", is_active=False)
    assert login(api, email="gone@example.com").status_code == 401


def test_login_is_rate_limited(api, user):
    statuses = [login(api, password="Wrong-Password-9").status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429  # the 11th attempt within a minute is refused


# ---------- profile ----------


def test_me_returns_the_logged_in_customer(auth_api, user):
    response = auth_api.get(ME)
    assert response.status_code == 200
    assert response.json()["email"] == user.email


@pytest.mark.parametrize(
    "header",
    [None, "Bearer not-a-jwt", "Token abc", "Bearer "],
    ids=["no-header", "garbage-token", "wrong-scheme", "empty-token"],
)
def test_me_rejects_requests_without_a_valid_token(api, db, header):
    if header:
        api.credentials(HTTP_AUTHORIZATION=header)
    assert api.get(ME).status_code == 401


def test_an_expired_access_token_is_rejected(api, user):
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=-timedelta(seconds=1))
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api.get(ME).status_code == 401


def test_a_tampered_token_is_rejected(api, user):
    token = str(AccessToken.for_user(user))
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}{'AA' if signature[-2:] != 'AA' else 'BB'}"
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered}")
    assert api.get(ME).status_code == 401


def test_a_refresh_token_cannot_be_used_as_an_access_token(api, user):
    refresh = login(api).json()["refresh"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh}")
    assert api.get(ME).status_code == 401


# ---------- refresh ----------


def test_refresh_gives_a_new_access_token_and_rotates_the_refresh_token(api, user):
    first = login(api).json()
    response = api.post(REFRESH, {"refresh": first["refresh"]}, format="json")
    assert response.status_code == 200
    assert response.json()["refresh"] != first["refresh"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    assert api.get(ME).status_code == 200


def test_an_old_refresh_token_stops_working_after_rotation(api, user):
    old = login(api).json()["refresh"]
    assert api.post(REFRESH, {"refresh": old}, format="json").status_code == 200
    # A stolen refresh token that was already used can't be replayed.
    assert api.post(REFRESH, {"refresh": old}, format="json").status_code == 401
