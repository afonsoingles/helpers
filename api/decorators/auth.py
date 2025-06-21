import os
from functools import wraps
from fastapi import Request
from api.utils.authTools import AuthenticationTools
import api.errors.exceptions as exceptions



auth = AuthenticationTools()



def authRequired(func):

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
        request.state.user = user


        return await func(*args, **kwargs)

    return wrapper
