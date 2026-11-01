"""DRF error handling: every failure leaves the API as JSON, never as an HTML debug page
(FastAPI logs response bodies, and an HTML page is 100+ KB).

  django ValidationError          -> 400  {"errors": [...]} or {"field": [...]}
  ObjectDoesNotExist / Http404    -> 404  {"detail": ...}
  IntegrityError                  -> 409  {"detail": ...}
  anything else (not an API error) -> 500  {"error": "internal_error"}, traceback in the log

DRF's own errors (401, 403, 405, 429 with Retry-After, ...) keep DRF's format.
ConflictError and ForbiddenError are for services: `raise ConflictError("Battle is full")`.
"""

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler, set_rollback

logger = logging.getLogger(__name__)


class ConflictError(exceptions.APIException):
    """409: the request is valid but clashes with the current state (battle is full, ...)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"


class ForbiddenError(exceptions.APIException):
    """403: the caller is known but may not do this (only the creator can start, ...)."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "forbidden"


def api_exception_handler(exc, context):
    view = context["view"].__class__.__name__
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(detail=as_serializer_error(exc))
    elif isinstance(exc, ObjectDoesNotExist):
        exc = exceptions.NotFound()
    elif isinstance(exc, IntegrityError):
        # first line only: the DETAIL line of a PostgreSQL error holds the offending values
        logger.warning("Integrity error in %s: %s", view, str(exc).partition("\n")[0])
        exc = ConflictError()

    response = exception_handler(exc, context)  # Http404, APIException (+ Retry-After)
    if response is not None:
        return response

    logger.exception("Unhandled exception in %s", view, exc_info=exc)
    set_rollback()
    return Response(
        {"error": "internal_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
