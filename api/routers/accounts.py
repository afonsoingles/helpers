from fastapi import APIRouter, Request
import api.errors.exceptions as exceptions
from api.utils.authTools import AuthenticationTools
from api.decorators.auth import authRequired


router = APIRouter()
authTools = AuthenticationTools()





@router.post("v1/accounts/login")
async def login(request: Request):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        raise exceptions.BadRequest("Email and password are required", "missing_fields")

    user = await authTools.get_raw_user(email)
    if not authTools.check_password(password, user["password"]):
        raise exceptions.BadRequest("Invalid password", "invalid_password")

    if user.get("blocked"):
        raise exceptions.Forbidden("User is blocked", "user_blocked")

    await authTools.invalidate_cache(email)
    token = authTools.create_token(email)
    return {"token": token}



@router.get("v1/accounts/me")
@authRequired
async def me(request: Request):
    return request.state.user

