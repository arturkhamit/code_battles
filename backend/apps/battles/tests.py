# ruff: noqa: S101, S105, S106
import time
import uuid

import jwt
import pytest

BATTLE = {
    "ranked": False,
    "type": "1v1",
    "task": 1,
    "duration": 15,
    "max_participants": 2,
}

# every route that only FastAPI may call
INTERNAL_ROUTES = [
    ("get", "/internal/battles/"),
    ("patch", "/internal/battles/join/1/"),
    ("patch", "/internal/battles/leave/1/"),
    ("patch", "/internal/battles/start/1/"),
    ("patch", "/internal/battles/finish/1/"),
    ("delete", "/internal/battles/delete/1/"),
    ("get", "/internal/tasks/"),
    ("get", "/internal/tasks/1/"),
]


def bearer(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def forge_access_token(user, key):
    """A well-formed simplejwt access token for `user`, signed with `key`."""
    now = int(time.time())
    claims = {
        "token_type": "access",
        "iat": now,
        "exp": now + 300,
        "jti": uuid.uuid4().hex,
        "user_id": user.pk,
    }
    return jwt.encode(claims, key, algorithm="HS256")


# --- internal API: Bearer INTERNAL_API_TOKEN -------------------------------


@pytest.mark.parametrize(("method", "path"), INTERNAL_ROUTES)
def test_internal_route_without_token_is_403(api, method, path):
    # no django_db mark: the check must not touch the database
    assert getattr(api, method)(path).status_code == 403


@pytest.mark.parametrize(
    "kind",
    ["wrong", "non_ascii", "django_secret", "jwt_key", "no_scheme", "wrong_scheme"],
)
def test_internal_route_with_bad_credentials_is_403(api, settings, kind):
    header = {
        "wrong": "Bearer not-the-token",
        "non_ascii": "Bearer токен",
        "django_secret": f"Bearer {settings.SECRET_KEY}",  # the old contract
        "jwt_key": f"Bearer {settings.JWT_SIGNING_KEY}",
        "no_scheme": settings.INTERNAL_API_TOKEN,
        "wrong_scheme": f"Token {settings.INTERNAL_API_TOKEN}",
    }[kind]
    response = api.get("/internal/battles/", HTTP_AUTHORIZATION=header)
    assert response.status_code == 403


@pytest.mark.django_db
def test_internal_route_with_valid_token_is_200(api, settings):
    response = api.get("/internal/battles/", **bearer(settings.INTERNAL_API_TOKEN))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_internal_delete_with_valid_token_reaches_the_view(api, settings):
    response = api.delete(
        "/internal/battles/delete/999999/", **bearer(settings.INTERNAL_API_TOKEN)
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Battle not found"}


# --- route split: old and misplaced paths are gone -------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/internal/accounts/login/"),
        ("post", "/api/internal/accounts/register/"),
        ("post", "/api/internal/battles/create/"),
        ("get", "/api/internal/battles/"),
        ("get", "/api/internal/tasks/1/"),
        # internal routes must not appear on the public side and vice versa
        ("patch", "/api/battles/join/1/"),
        ("get", "/api/battles/"),
        ("post", "/internal/battles/create/"),
        ("post", "/internal/accounts/login/"),
    ],
)
def test_old_and_misplaced_paths_are_404(api, settings, method, path):
    response = getattr(api, method)(path, **bearer(settings.INTERNAL_API_TOKEN))
    assert response.status_code == 404


# --- public API: JWT signed with JWT_SIGNING_KEY ---------------------------


@pytest.mark.django_db
def test_battle_create_without_token_is_401(api):
    assert api.post("/api/battles/create/", BATTLE, format="json").status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("key_name", ["INTERNAL_API_TOKEN", "SECRET_KEY"])
def test_jwt_signed_with_another_secret_is_rejected(api, settings, user, key_name):
    token = forge_access_token(user, getattr(settings, key_name))
    response = api.post(
        "/api/battles/create/", BATTLE, format="json", **bearer(token)
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_jwt_signed_with_jwt_signing_key_is_accepted(api, settings, user, task):
    # same claims as the rejected tokens above; only the key differs
    token = forge_access_token(user, settings.JWT_SIGNING_KEY)
    response = api.post(
        "/api/battles/create/", BATTLE, format="json", **bearer(token)
    )
    assert response.status_code == 201
    assert response.json()["id"]


# --- throttling: battles created per user ----------------------------------


@pytest.mark.django_db
def test_battle_create_is_limited_to_30_an_hour_per_user(
    api, settings, user, django_user_model, task
):
    def create(account):
        token = forge_access_token(account, settings.JWT_SIGNING_KEY)
        return api.post("/api/battles/create/", BATTLE, format="json", **bearer(token))

    for _ in range(30):
        assert create(user).status_code == 201

    throttled = create(user)
    assert throttled.status_code == 429
    assert throttled["Content-Type"].startswith("application/json")
    assert int(throttled["Retry-After"]) > 0

    # the limit is per user, not per IP: another account on the same address is not affected
    other = django_user_model.objects.create_user(
        username="player_two", email="player.two@example.com", password="S3cure-pass!"
    )
    assert create(other).status_code == 201
