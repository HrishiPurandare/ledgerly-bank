import pytest

from banking.iban import format_iban, is_valid_uae_iban, make_uae_iban

KNOWN_VALID = "AE070331234567890123456"  # the published example UAE IBAN


def test_a_published_uae_iban_is_valid():
    assert is_valid_uae_iban(KNOWN_VALID)


@pytest.mark.parametrize(
    "iban",
    [
        "AE070331234567890123457",  # one digit changed: mod-97 catches typos
        "AE07033123456789012345",  # 22 characters
        "AE0703312345678901234567",  # 24 characters
        "GB070331234567890123456",  # not a UAE IBAN
        "AE07033123456789012345X",  # letter in the account number
        "",
    ],
    ids=["typo", "too-short", "too-long", "wrong-country", "letter", "empty"],
)
def test_invalid_ibans_are_rejected(iban):
    assert not is_valid_uae_iban(iban)


def test_spaces_and_lower_case_are_accepted_as_people_type_them():
    assert is_valid_uae_iban("ae07 0331 2345 6789 0123 456")


def test_generated_ibans_are_valid_and_23_characters():
    iban = make_uae_iban("1234567890123456")
    assert len(iban) == 23 and iban[4:7] == "999" and is_valid_uae_iban(iban)  # AE + check digits + bank


def test_account_number_must_be_16_digits():
    with pytest.raises(ValueError):
        make_uae_iban("123")


def test_display_format_groups_of_four():
    assert format_iban(KNOWN_VALID) == "AE07 0331 2345 6789 0123 456"
