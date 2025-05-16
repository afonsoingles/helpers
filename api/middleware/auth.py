from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse
from api.utils.authDb import AuthenticationDb
import re

auth = AuthenticationDb()

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, protected_paths=None):
        super().__init__(app)
        self.protected_paths = protected_paths or []

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self._is_protected(path):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse({"detail": "Cabeçalho de autorização ausente"}, status_code=401)

            token = auth_header.split(" ")[1]
            try:
                email = await auth.decode_token(token)
                user = await auth.get_user(email)
                request.state.user = user
            except Exception as e:
                return JSONResponse({"detail": str(e)}, status_code=401)

        return await call_next(request)

    def _is_protected(self, path: str):
        for protected in self.protected_paths:
            if re.match(protected, path):
                return True
        return False
