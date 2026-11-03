import logging

from redis.exceptions import RedisError
from rest_framework.throttling import UserRateThrottle

logger = logging.getLogger(__name__)


class _FailOpenThrottle(UserRateThrottle):
    """Counters live in Redis. If it is down the request goes through unlimited: a lobby
    that cannot be created or looked up because of a cache outage is worse than a missed limit."""

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except RedisError as exc:
            logger.warning("Throttle %s skipped, Redis is unavailable: %s", self.scope, exc)
            return True


class BattleCreateThrottle(_FailOpenThrottle):
    """Battles created per user (rate: DEFAULT_THROTTLE_RATES["battle_create"]), counted in Redis."""

    scope = "battle_create"


class InviteLookupThrottle(_FailOpenThrottle):
    """Invite code lookups per user: stops guessing the codes of private battles."""

    scope = "invite_lookup"
