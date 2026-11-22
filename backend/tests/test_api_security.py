"""Secure by default: every endpoint in the OpenAPI schema needs a login, unless it's on this short list.

New endpoints are picked up automatically, so a forgotten permission class fails this test.
"""

import re

import pytest
from drf_spectacular.generators import SchemaGenerator

PUBLIC = {
    ("GET", "/api/health/"),
    ("POST", "/api/auth/register/"),
    ("POST", "/api/auth/login/"),
    ("POST", "/api/auth/refresh/"),
}


def schema_operations():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    for path, methods in schema["paths"].items():
        for method in methods:
            yield method.upper(), path


OPERATIONS = sorted(schema_operations())


def test_the_schema_lists_the_public_endpoints():
    assert PUBLIC <= set(OPERATIONS)


@pytest.mark.parametrize(("method", "path"), [op for op in OPERATIONS if op not in PUBLIC])
def test_private_endpoints_reject_anonymous_requests(api, db, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)  # /accounts/{id}/ -> /accounts/1/
    response = api.generic(method, url)
    assert response.status_code == 401, f"{method} {path} answered {response.status_code} without a login"


def test_api_docs_are_public(api, db):
    assert api.get("/api/schema/").status_code == 200
    assert api.get("/api/docs/").status_code == 200
