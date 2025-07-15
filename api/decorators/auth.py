import os
from functools import wraps
from fastapi import Request
from api.utils.authTools import AuthenticationTools
import api.errors.exceptions as exceptions



auth = AuthenticationTools()


def authRequired(func=None, *, admin: bool = False, allowBanned: bool = False):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request") or next(
                (v for v in args if isinstance(v, Request)), None
            )
            if not request:
                raise RuntimeError("Cannot find request in args or kwargs")

            auth_header = (
                request.headers.get("Authorization")
                or request.headers.get("authorization")
            )
            if not auth_header or not auth_header.startswith("Bearer "):
                raise exceptions.BadRequest(
                    message="No authentication token provided",
                    type="missing_token"
                )

            token = auth_header.split(" ", 1)[1]

            email = await auth.decode_token(token)

            user = await auth.get_user_by_email(email)
            if not user:
                raise exceptions.Unauthorized(
                    message="Invalid authentication token",
                    type="invalid_token"
                )
            
            if user.get("status") == "suspended" and not allowBanned:
                raise exceptions.Forbidden(
                    message="User account is suspended",
                    type="account_blocked"
                )
            request.state.user = user

            if admin and not user.get("admin", False):
                raise exceptions.Forbidden(
                    message="Admin privileges required",
                    type="admin_required"
                )

            return await func(*args, **kwargs)

        return wrapper

    if func:
        return decorator(func)
    return decorator
