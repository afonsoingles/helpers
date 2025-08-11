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

            authHeader = (
                request.headers.get("Authorization")
                or request.headers.get("authorization")
            )
            if not authHeader or not authHeader.startswith("Bearer "):
                raise exceptions.BadRequest(
                    message="No authentication token provided",
                    type="missing_token"
                )

            token = authHeader.split(" ", 1)[1]
            email = await auth.decode_token(token)
            user = await auth.get_user_by_email(email)
            if not user:
                raise exceptions.Unauthorized(
                    message="Invalid authentication token",
                    type="invalid_token"
                )

            

            request.state.user = user
            request.state.impersonatedBy = None

            impersonateId = request.headers.get("X-Impersonate-User")
            if user.get("admin", False) and impersonateId:
                targetUser = await auth.get_user_by_id(impersonateId)
                if targetUser:
                    request.state.user = targetUser
                    request.state.impersonatedBy = user.get("id")
                    
            if request.state.user.get("status") == "suspended" and not allowBanned:
                raise exceptions.Forbidden(
                    message="User account is suspended",
                    type="account_blocked"
                )
            
            if request.state.user.get("status") == "deletionPending" and not allowBanned:
                raise exceptions.Forbidden(
                    message="User account is pending deletion",
                    type="account_pending_deletion"
                )
            
            
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
