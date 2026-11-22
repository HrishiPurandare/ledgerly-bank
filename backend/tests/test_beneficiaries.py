"""Adding a beneficiary: IBAN rules, the 100 limit, and OTP confirmation (expiry, 3 attempts, lock)."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone

from payments.models import Beneficiary

URL = "/api/beneficiaries/"
OMAR_IBAN = "AE070331234567890123456"  # a valid IBAN at another UAE bank


def add(api, iban=OMAR_IBAN, name="Omar Ali"):
    return api.post(URL, {"name": name, "iban": iban}, format="json")


def code_from(mailoutbox) -> str:
    return re.search(r"\b(\d{6})\b", mailoutbox[-1].body).group(1)


def confirm(api, beneficiary_id, code):
    return api.post(f"{URL}{beneficiary_id}/confirm/", {"otp": code}, format="json")


def test_adding_a_beneficiary_emails_an_otp_and_keeps_it_pending(auth_api, user, mailoutbox):
    response = add(auth_api)
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [user.email]
    code = code_from(mailoutbox)
    assert code not in response.content.decode()  # the code only travels by email
    stored = Beneficiary.objects.get()
    assert stored.otp_hash and code not in stored.otp_hash  # hashed at rest


def test_the_emailed_code_activates_the_beneficiary(auth_api, mailoutbox):
    beneficiary_id = add(auth_api).json()["id"]
    response = confirm(auth_api, beneficiary_id, code_from(mailoutbox))
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE" and response.json()["activated_at"]


def test_three_wrong_codes_lock_the_beneficiary_even_for_the_right_code(auth_api, mailoutbox):
    beneficiary_id = add(auth_api).json()["id"]
    right = code_from(mailoutbox)
    wrong = "000000" if right != "000000" else "111111"
    first, second = confirm(auth_api, beneficiary_id, wrong), confirm(auth_api, beneficiary_id, wrong)
    assert (first.json()["code"], second.json()["code"]) == ("otp_invalid", "otp_invalid")
    assert "1 attempt(s) left" in second.json()["detail"]
    assert confirm(auth_api, beneficiary_id, wrong).json()["code"] == "otp_locked"
    late = confirm(auth_api, beneficiary_id, right)
    assert late.status_code == 400 and late.json()["code"] == "otp_locked"


def test_wrong_attempts_are_saved_although_the_request_fails(auth_api, mailoutbox):
    beneficiary_id = add(auth_api).json()["id"]
    confirm(auth_api, beneficiary_id, "999999" if code_from(mailoutbox) != "999999" else "888888")
    assert Beneficiary.objects.get(pk=beneficiary_id).otp_attempts == 1  # no rollback on the error


def test_an_expired_code_is_rejected(auth_api, mailoutbox):
    beneficiary_id = add(auth_api).json()["id"]
    Beneficiary.objects.filter(pk=beneficiary_id).update(otp_expires_at=timezone.now() - timedelta(seconds=1))
    response = confirm(auth_api, beneficiary_id, code_from(mailoutbox))
    assert response.json()["code"] == "otp_expired"


def test_confirming_twice_is_rejected(auth_api, mailoutbox):
    beneficiary_id = add(auth_api).json()["id"]
    code = code_from(mailoutbox)
    confirm(auth_api, beneficiary_id, code)
    assert confirm(auth_api, beneficiary_id, code).json()["code"] == "already_active"


@pytest.mark.parametrize("otp", ["12345", "1234567", "abcdef", ""])
def test_the_code_must_be_six_digits(auth_api, mailoutbox, otp):
    beneficiary_id = add(auth_api).json()["id"]
    assert confirm(auth_api, beneficiary_id, otp).status_code == 400
    assert Beneficiary.objects.get(pk=beneficiary_id).otp_attempts == 0  # a typo isn't a guess


@pytest.mark.parametrize(
    "iban",
    ["AE070331234567890123457", "GB29NWBK60161331926819", "AE07033123456789012345"],
    ids=["bad-checksum", "not-uae", "too-short"],
)
def test_invalid_ibans_are_rejected(auth_api, iban):
    response = add(auth_api, iban=iban)
    assert response.status_code == 400 and response.json()["code"] == "invalid_iban"


def test_iban_is_normalised_as_people_type_it(auth_api):
    response = add(auth_api, iban="ae07 0331 2345 6789 0123 456")
    assert response.status_code == 201 and response.json()["iban"] == OMAR_IBAN


def test_duplicate_beneficiary_is_rejected(auth_api):
    add(auth_api)
    assert add(auth_api, iban="AE07 0331 2345 6789 0123 456").json()["code"] == "duplicate_beneficiary"


def test_own_account_cannot_be_a_beneficiary(auth_api, user, make_account):
    account = make_account(user)
    assert add(auth_api, iban=account.iban).json()["code"] == "own_account"


def test_the_hundredth_beneficiary_is_allowed_and_the_hundred_and_first_is_not(auth_api, user):
    from banking.iban import make_uae_iban

    Beneficiary.objects.bulk_create(
        Beneficiary(owner=user, name=f"B{i}", iban=make_uae_iban(f"{i:016d}")) for i in range(99)
    )
    assert add(auth_api).status_code == 201  # number 100
    response = add(auth_api, iban=make_uae_iban(f"{500:016d}"))
    assert response.status_code == 400 and response.json()["code"] == "too_many_beneficiaries"


def test_other_customers_beneficiaries_are_invisible(auth_api, make_user):
    other = make_user(email="other@example.com")
    theirs = Beneficiary.objects.create(owner=other, name="X", iban=OMAR_IBAN)
    assert auth_api.get(URL).json()["count"] == 0
    assert auth_api.get(f"{URL}{theirs.id}/").status_code == 404
    assert confirm(auth_api, theirs.id, "123456").status_code == 404
    assert auth_api.delete(f"{URL}{theirs.id}/").status_code == 404
    assert Beneficiary.objects.filter(pk=theirs.id).exists()
