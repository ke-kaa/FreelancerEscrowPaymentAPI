"""Smoke — register, login, refresh."""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.django_db]

REGISTER_URL = "/api/account/register/"
TOKEN_URL = "/api/account/token/"
REFRESH_URL = "/api/account/token/refresh/"


def _register_payload(email="smoke_user@example.com"):
    return {
        "email": email,
        "password": "Sup3rStr0ng!pw",
        "confirm_password": "Sup3rStr0ng!pw",
        "first_name": "Smoke",
        "last_name": "Test",
        "user_type": "client",
        "country": "US",
    }


def test_register_returns_201(api_client):
    r = api_client.post(REGISTER_URL, _register_payload(), format="json")
    assert r.status_code == 201, r.content


def test_register_then_login_obtains_tokens(api_client):
    payload = _register_payload(email="login_smoke@example.com")
    assert api_client.post(REGISTER_URL, payload, format="json").status_code == 201

    r = api_client.post(
        TOKEN_URL,
        {"email": payload["email"], "password": payload["password"]},
        format="json",
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert "access" in body
    assert "refresh" in body


def test_refresh_returns_new_access(api_client):
    payload = _register_payload(email="refresh_smoke@example.com")
    api_client.post(REGISTER_URL, payload, format="json")
    tokens = api_client.post(
        TOKEN_URL,
        {"email": payload["email"], "password": payload["password"]},
        format="json",
    ).json()

    r = api_client.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
    assert r.status_code == 200, r.content
    assert "access" in r.json()
