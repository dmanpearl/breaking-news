from ninja.security import HttpBearer

from .models import APIKey


class APIKeyAuth(HttpBearer):
    """
    Authenticates requests using a Bearer token in the Authorization header.

        Authorization: Bearer <plaintext_key>

    Returns the APIKey instance on success.
    Returns None (→ 401) if the key is invalid, inactive, or the owner is
    inactive.
    Raises HttpError 401 with a descriptive body if the key is valid but the
    request origin is not in the key's allowed_origins list.
    """

    def authenticate(self, request, token: str):
        from ninja.errors import HttpError

        result = APIKey.authenticate(token, request=request)

        if result is None:
            return None  # Django Ninja converts this to a plain 401

        if isinstance(result, tuple) and result[0] == "origin_rejected":
            detected_origin = result[1] or "(no origin header)"
            raise HttpError(
                401,
                f"This API key is restricted to specific origins. "
                f"Detected origin: {detected_origin}. "
                f"Ask your administrator to add this origin to the key's allowed list.",
            )

        return result  # APIKey instance — auth succeeded
