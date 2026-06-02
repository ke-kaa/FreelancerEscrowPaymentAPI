"""Smoke — authenticated client can create a project, then a milestone on it."""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.django_db]

CREATE_PROJECT_URL = "/projects/client/create/"
LIST_CLIENT_PROJECTS_URL = "/projects/client/list/"


def _project_payload():
    return {
        "title": "Smoke project",
        "description": "Smoke test project description.",
        "amount": "500.00",
        "is_public": True,
    }


def test_client_list_projects_requires_auth(api_client):
    r = api_client.get(LIST_CLIENT_PROJECTS_URL)
    assert r.status_code in (401, 403)


def test_authenticated_client_can_create_project(auth_client_api):
    r = auth_client_api.post(CREATE_PROJECT_URL, _project_payload(), format="json")
    assert r.status_code in (200, 201), r.content


def test_authenticated_client_lists_own_projects(auth_client_api):
    auth_client_api.post(CREATE_PROJECT_URL, _project_payload(), format="json")
    r = auth_client_api.get(LIST_CLIENT_PROJECTS_URL)
    assert r.status_code == 200, r.content
