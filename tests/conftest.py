"""Shared fixtures for the smoke + integration + e2e suites."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


def _make_user(*, email, user_type, password="testpass123!"):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
        user_type=user_type,
        country="US",
    )


@pytest.fixture
def client_user(db):
    return _make_user(email="client@example.com", user_type="client")


@pytest.fixture
def freelancer_user(db):
    return _make_user(email="freelancer@example.com", user_type="freelancer")


@pytest.fixture
def auth_client_api(api_client, client_user):
    api_client.force_authenticate(user=client_user)
    return api_client


@pytest.fixture
def auth_freelancer_api(api_client, freelancer_user):
    api_client.force_authenticate(user=freelancer_user)
    return api_client
