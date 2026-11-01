# ruff: noqa: S101, S105, S106
import jwt
import pytest
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.models import Profile

REGISTER_URL = "/api/accounts/register/"
LOGIN_URL = "/api/accounts/login/"
REFRESH_URL = "/api/accounts/refresh/"
LOGOUT_URL = "/api/accounts/logout/"

REGISTER = {
    "username": "player_one",
    "email": "player.one@example.com",
    "password1": "S3cure-pass!",
    "password2": "S3cure-pass!",
}
CREDENTIALS = {"username": "player_one", "password": "S3cure-pass!"}


def register(api, **overrides):
    return api.post(REGISTER_URL, {**REGISTER, **overrides}, format="json")


def login(api, **body):
    return api.post(LOGIN_URL, body or CREDENTIALS, format="json")


def bad_login(api, username="ghost_user", **environ):
    return api.post(
        LOGIN_URL, {"username": username, "password": "wrong-pass"}, format="json", **environ
    )


def refresh(api, token):
    return api.post(REFRESH_URL, {"refresh": token}, format="json")


def assert_throttled(response):
    assert response.status_code == 429
    assert response["Content-Type"].startswith("application/json")
    assert int(response["Retry-After"]) > 0
    assert "throttled" in response.json()["detail"]


# --- the whole cycle --------------------------------------------------------


@pytest.mark.django_db
def test_register_login_refresh_logout_on_public_paths(api, settings):
    assert register(api).status_code == 201

    login_response = login(api)
    assert login_response.status_code == 200
    tokens = login_response.json()

    # FastAPI verifies access tokens with JWT_SIGNING_KEY, not with Django's SECRET_KEY
    claims = jwt.decode(tokens["access"], settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    assert claims["token_type"] == "access"
    assert claims["username"] == "player_one"
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(tokens["access"], settings.SECRET_KEY, algorithms=["HS256"])

    refreshed = refresh(api, tokens["refresh"])
    assert refreshed.status_code == 200
    rotated = refreshed.json()
    assert rotated["refresh"] != tokens["refresh"]  # the refresh token is rotated

    # logging out needs the newest refresh token; the one it replaced is dead
    assert api.post(LOGOUT_URL, {"refresh": tokens["refresh"]}, format="json").status_code == 400
    assert api.post(LOGOUT_URL, {"refresh": rotated["refresh"]}, format="json").status_code == 200


# --- registration -----------------------------------------------------------


@pytest.mark.django_db
def test_register_creates_user_and_profile_with_empty_avatar(api, django_user_model):
    response = register(api, email="a@b.co")  # 6 characters: the old "at least 12" rule is gone
    assert response.status_code == 201
    assert response.json() == {"id": response.json()["id"], "username": "player_one", "email": "a@b.co"}
    assert Profile.objects.get(user_id=response.json()["id"]).avatar == ""
    assert django_user_model.objects.get(username="player_one").check_password("S3cure-pass!")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"email": "no-at-sign-in-here"}, "email"),
        ({"email": "two@@example.com"}, "email"),
        ({"email": "user@nodot"}, "email"),
        ({"email": ""}, "email"),
        ({"email": "a" * 96 + "@b.co"}, "email"),  # 101 characters
        ({"password1": "12345678", "password2": "12345678"}, "password1"),  # numeric
        ({"password1": "password", "password2": "password"}, "password1"),  # common
        ({"password1": "player_one", "password2": "player_one"}, "password1"),  # = username
        ({"password1": "short1!", "password2": "short1!"}, "password1"),
        ({"password2": "Different-pass1!"}, "password2"),
    ],
)
def test_register_rejects_bad_input_with_a_400_per_field(
    api, django_user_model, overrides, field
):
    response = register(api, **overrides)
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")
    assert field in response.json()
    assert not django_user_model.objects.exists()


@pytest.mark.django_db
def test_register_lists_every_password_validator_failure(api):
    response = register(api, password1="12345678", password2="12345678")
    assert response.json()["password1"] == [
        "This password is too common.",
        "This password is entirely numeric.",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("overrides", "field"),
    [({"email": "other@example.com"}, "username"), ({"username": "player_two"}, "email")],
)
def test_register_rejects_a_taken_username_or_email(api, user, overrides, field):
    response = register(api, **overrides)
    assert response.status_code == 400
    assert field in response.json()


# --- login ------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {"username": "player_one", "password": "wrong-pass"},
        {"username": "ghost_user", "password": "S3cure-pass!"},
    ],
)
def test_login_with_wrong_credentials_is_401_not_400(api, user, body):
    response = login(api, **body)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert response["WWW-Authenticate"]


@pytest.mark.django_db
def test_login_of_an_inactive_user_is_401(api, user):
    user.is_active = False
    user.save()
    assert login(api).status_code == 401


@pytest.mark.django_db
def test_login_with_missing_fields_is_400(api):
    response = login(api, username="player_one")
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.django_db
def test_login_with_malformed_json_is_400_not_500(api):
    # the username throttle reads the body before the view does
    response = api.post(LOGIN_URL, "{bad json", content_type="application/json")
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")


@pytest.mark.django_db
def test_login_sets_last_login_and_saving_the_user_does_not(api, user):
    assert user.last_login is None  # no auto_now

    assert login(api).status_code == 200
    user.refresh_from_db()
    stamp = user.last_login
    assert stamp is not None

    user.first_name = "Player"
    user.save()
    user.refresh_from_db()
    assert user.last_login == stamp


# --- refresh token rotation -------------------------------------------------


@pytest.mark.django_db
def test_refresh_returns_a_new_pair_and_blacklists_the_old_refresh_token(api, user, settings):
    tokens = login(api).json()

    first = refresh(api, tokens["refresh"])
    assert first.status_code == 200
    rotated = first.json()
    assert set(rotated) == {"access", "refresh"}
    claims = jwt.decode(rotated["access"], settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    assert claims["username"] == "player_one"  # claims survive the rotation

    replay = refresh(api, tokens["refresh"])
    assert replay.status_code == 400
    assert "refresh" in replay.json()

    second = refresh(api, rotated["refresh"])  # the chain goes on with the new token
    assert second.status_code == 200
    assert BlacklistedToken.objects.count() == 2


@pytest.mark.django_db
def test_refresh_with_a_garbage_token_is_400(api):
    response = refresh(api, "not-a-token")
    assert response.status_code == 400
    assert response.json() == {"refresh": ["Invalid or expired refresh token"]}


@pytest.mark.django_db
def test_refresh_of_a_deleted_user_is_400_not_404(api, user):
    tokens = login(api).json()
    user.delete()
    response = refresh(api, tokens["refresh"])
    assert response.status_code == 400
    assert "refresh" in response.json()


# --- permissions ------------------------------------------------------------


def test_a_view_without_permission_classes_is_closed_to_anonymous_users():
    class Forgetful(APIView):
        def get(self, request):
            return Response("secret")

    response = Forgetful.as_view()(APIRequestFactory().get("/"))
    assert response.status_code == 401


# --- throttling (Redis-backed DRF throttles) --------------------------------


@pytest.mark.django_db
def test_login_is_limited_to_10_a_minute_per_ip(api, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    # a new username every time: only the per-IP limit can fire here
    statuses = [bad_login(api, f"ghost_{i}").status_code for i in range(10)]
    assert statuses == [401] * 10

    assert_throttled(bad_login(api, "ghost_10"))
    assert bad_login(api, "ghost_11", REMOTE_ADDR="10.1.2.3").status_code == 401  # other IP


@pytest.mark.django_db
def test_login_ip_limit_cannot_be_dodged_with_a_forged_x_forwarded_for(api, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    for i in range(10):
        response = bad_login(api, f"ghost_{i}", HTTP_X_FORWARDED_FOR=f"6.6.6.{i}")
        assert response.status_code == 401
    assert_throttled(bad_login(api, "ghost_10", HTTP_X_FORWARDED_FOR="6.6.6.99"))


@pytest.mark.django_db
def test_login_ip_limit_cannot_be_lifted_by_sending_an_access_token(api, user, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
    access = login(api).json()["access"]
    for i in range(9):  # the login above was request number 1
        response = bad_login(api, f"ghost_{i}", HTTP_AUTHORIZATION=f"Bearer {access}")
        assert response.status_code == 401
    assert_throttled(bad_login(api, "ghost_9", HTTP_AUTHORIZATION=f"Bearer {access}"))


@pytest.mark.django_db
def test_num_proxies_takes_the_client_ip_from_the_right_of_x_forwarded_for(api, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    for i in range(10):  # the left part is whatever the client wrote; the proxy added 9.9.9.9
        response = bad_login(api, f"ghost_{i}", HTTP_X_FORWARDED_FOR=f"{i}.{i}.{i}.{i}, 9.9.9.9")
        assert response.status_code == 401
    assert_throttled(bad_login(api, "ghost_10", HTTP_X_FORWARDED_FOR="7.7.7.7, 9.9.9.9"))

    other_client = bad_login(api, "ghost_11", HTTP_X_FORWARDED_FOR="7.7.7.7, 9.9.9.8")
    assert other_client.status_code == 401


@pytest.mark.django_db
def test_login_is_limited_to_5_a_minute_per_username_from_any_ip(api):
    spellings = ["victim_user", " Victim_User", "VICTIM_USER ", "victim_USER", "ViCtIm_UsEr"]
    for i, name in enumerate(spellings):  # every attempt from another IP
        assert bad_login(api, name, REMOTE_ADDR=f"10.0.0.{i}").status_code == 401

    assert_throttled(bad_login(api, "victim_user", REMOTE_ADDR="10.0.0.99"))
    assert bad_login(api, "someone_else", REMOTE_ADDR="10.0.0.98").status_code == 401


@pytest.mark.django_db
def test_login_username_limit_treats_a_number_like_its_string(api):
    for i, name in enumerate(["12345", 12345, "12345", 12345, "12345"]):
        response = api.post(
            LOGIN_URL,
            {"username": name, "password": "wrong-pass"},
            format="json",
            REMOTE_ADDR=f"10.0.1.{i}",
        )
        assert response.status_code == 401
    assert_throttled(bad_login(api, "12345", REMOTE_ADDR="10.0.1.99"))


@pytest.mark.django_db
@pytest.mark.parametrize("body", [{}, [], {"username": None}, {"username": True}, {"username": {}}])
def test_login_username_throttle_ignores_a_body_without_a_username(api, body):
    response = api.post(LOGIN_URL, body, format="json")
    assert response.status_code == 400  # from the serializer, not a crash in the throttle


@pytest.mark.django_db
def test_register_is_limited_to_10_an_hour_per_ip(api):
    for _ in range(10):
        assert register(api, email="not-an-email").status_code == 400  # counts as well
    assert_throttled(register(api))
    other_ip = api.post(REGISTER_URL, REGISTER, format="json", REMOTE_ADDR="10.2.3.4")
    assert other_ip.status_code == 201


@pytest.mark.django_db
def test_refresh_is_limited_to_30_a_minute_per_ip(api):
    for _ in range(30):
        assert refresh(api, "not-a-token").status_code == 400
    assert_throttled(refresh(api, "not-a-token"))
