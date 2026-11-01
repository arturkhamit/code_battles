"""Throttles of the auth endpoints. Rates are in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"];
counters live in the Django cache (Redis). The client IP honours REST_FRAMEWORK["NUM_PROXIES"].
"""

import hashlib

from rest_framework.throttling import SimpleRateThrottle


class IPThrottle(SimpleRateThrottle):
    """Per client IP. Unlike AnonRateThrottle it also counts requests that carry a valid
    token, so attaching any access token does not lift the limit."""

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginIPThrottle(IPThrottle):
    scope = "login_ip"


class RegisterThrottle(IPThrottle):
    scope = "register"


class RefreshThrottle(IPThrottle):
    scope = "refresh"


class LoginUsernameThrottle(SimpleRateThrottle):
    """Per username in the body, whatever the IP: stops a distributed guess of one password."""

    scope = "login_user"

    def get_cache_key(self, request, view):
        data = request.data
        username = data.get("username") if isinstance(data, dict) else None
        # same input types as the serializer's CharField; anything else is a 400 there
        if isinstance(username, bool) or not isinstance(username, (str, int, float)):
            return None
        # the serializer trims the username, and "Alice" / "alice" must not be separate budgets
        normalized = str(username).strip().casefold()
        # hashed: unbounded user input never becomes a Redis key as is
        ident = hashlib.sha256(normalized.encode(errors="replace")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}
