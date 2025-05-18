from fastapi import APIRouter, Request
import api.errors.exceptions as exceptions
from api.utils.authTools import AuthenticationTools
from api.decorators.auth import authRequired


router = APIRouter()
authTools = AuthenticationTools()



@router.post("/signup")
async def signup(request: Request):
    body = await request.json()
    email = body.get("email")
    username = body.get("username")
    password = body.get("password")

    if not email or not username or not password:
        raise exceptions.BadRequest("Email, username and password are required", "missing_fields")

    try:
        existingAccount = await authTools.get_user(email)
        if existingAccount["username"] == username:
            raise exceptions.BadRequest("A account with this username already exists", "username_in_use")
        
        return exceptions.BadRequest("A account with this email already exists", "email_in_use")
    except exceptions.NotFound:
        pass


    await authTools.create_user(username, email, password)
    
    token = authTools.create_token(email)
    return {"token": token}



@router.post("/login")
async def login(request: Request):
    body = await request.json()
    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        raise exceptions.BadRequest("Email and password are required", "missing_fields")

    user = await authTools.get_user(email)
    if not authTools.check_password(password, user["password"]):
        raise exceptions.BadRequest("Invalid password", "invalid_password")

    if user.get("blocked"):
        raise exceptions.Forbidden("User is blocked", "user_blocked")

    await authTools.invalidate_cache(email)
    token = authTools.create_token(email)
    return {"token": token}



@router.get("/me")
@authRequired
async def me(request: Request):
    return request.state.user

