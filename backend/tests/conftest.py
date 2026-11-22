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
