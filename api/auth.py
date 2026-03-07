from ninja.security import HttpBearer

from .models import APIKey


class APIKeyAuth(HttpBearer):
    """
    Authenticates requests using a Bearer token in the Authorization header.

        Authorization: Bearer <plaintext_key>

    Returns the APIKey instance on success, None on failure.
    Django Ninja automatically returns 401 when None is returned.
    """

    def authenticate(self, request, token: str):
        return APIKey.authenticate(token, request=request)
