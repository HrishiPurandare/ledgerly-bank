import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

PASSWORD = "Corr3ct-Horse-Battery"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Rate limits are counted in the cache; without this, one test's logins leak into the next."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(db, django_user_model):
    def make(email="sara@example.com", full_name="Sara Khan", password=PASSWORD, **extra):
        return django_user_model.objects.create_user(
            email=email, full_name=full_name, password=password, **extra
        )

    return make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def auth_api(api, user):
    """A client logged in as `user` through the real login endpoint, not a shortcut."""
    response = api.post("/api/auth/login/", {"email": user.email, "password": PASSWORD}, format="json")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api


@pytest.fixture
def make_account(db):
    from banking.iban import make_uae_iban
    from banking.models import Account

    counter = iter(range(10**15, 10**16))

    def make(owner, type="CURRENT", balance="0.00", **extra):
        from decimal import Decimal

        return Account.objects.create(
            owner=owner, iban=make_uae_iban(str(next(counter))), type=type, balance=Decimal(balance), **extra
        )

    return make


@pytest.fixture
def add_tx(db):
    """Append a transaction and keep the account balance and balance_after consistent."""
    from decimal import Decimal

    from django.utils import timezone

    from banking.models import Transaction

    counter = iter(range(1, 10**6))

    def add(
        account, amount, direction="DEBIT", category="CARD", description="Card purchase", when=None, **extra
    ):
        amount = Decimal(str(amount))
        account.balance += amount if direction == "CREDIT" else -amount
        account.save(update_fields=["balance"])
        return Transaction.objects.create(
            account=account,
            direction=direction,
            category=category,
            amount=amount,
            balance_after=account.balance,
            description=description,
            reference=f"T{next(counter):08d}",
            created_at=when or timezone.now(),
            **extra,
        )

    return add
