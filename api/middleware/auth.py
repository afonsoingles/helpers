from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse
from api.utils.authTools import AuthenticationTools
import api.errors.exceptions as exceptions
from api.config import AUTH_ROUTES

auth = AuthenticationTools()

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not any(path.startswith(prefix) for prefix in AUTH_ROUTES):
            return await call_next(request)

        auth_header = (
            request.headers.get("Authorization")
            or request.headers.get("authorization")
        )
        if not auth_header or not auth_header.startswith("Bearer "):
            err = exceptions.BadRequest(
                message="No authentication token provided",
                type="missing_token"
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": err.message, "type": err.type}
            )

        token = auth_header.split(" ", 1)[1]

        email = await auth.decode_token(token)
        user  = await auth.get_user(email)
        request.state.user = user


        return await call_next(request)