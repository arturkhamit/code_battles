from django.conf import settings
from rest_framework import permissions


class IsInternalService(permissions.BasePermission):
    def has_permission(self, request, view):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return False

        parts = auth_header.split()
        if len(parts) != 2:
            return False

        prefix, token = parts

        return prefix == "Bearer" and token == settings.SECRET_KEY
