import os
from fastapi import APIRouter, Request
import api.errors.exceptions as exceptions
from api.utils.authTools import AuthenticationTools
from api.decorators.auth import authRequired
from datetime import datetime
import pytz


router = APIRouter()
authTools = AuthenticationTools()




@router.get("/v2/accounts/me", status_code=200)
@router.get("/v1/accounts/me", status_code=200)
@authRequired
async def me(request: Request):
    return request.state.user


@router.post("/v2/accounts/signup", status_code=201)
async def v2_signup(request: Request):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    currentTime = datetime.now(pytz.timezone(os.environ.get("TIMEZONE")))

    userData = {
        "name": body.get("name"),
        "username": body.get("username"),
        "email": body.get("email"),
        "passwordHash": authTools.hash_password(body.get("password")),
        "admin": False,
        "status": "active",
        "timezone": body.get("timezone", os.environ.get("TIMEZONE")),
        "pushConfiguration": [],
        "services": [],
        "createdAt": int(currentTime.timestamp()),
        "updatedAt": int(currentTime.timestamp()),
    }

    if not userData["name"] or not userData["username"] or not userData["email"] or not userData["passwordHash"]:
        raise exceptions.BadRequest("All fields are required", "missing_fields")
    
    if await authTools.get_user_by_email(userData["email"]):
        raise exceptions.BadRequest("This email is already registered", "email_taken")

    if await authTools.get_user_by_username(userData["username"]):
        raise exceptions.BadRequest("This username is already taken", "username_taken")
    
    await authTools.create_user(userData)
    
    return {"success": True, "message": "User created successfully. You can now log in."}


@router.post("/v2/accounts/login", status_code=200)
async def v2_login(request: Request):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    email = body.get("email")
    password = body.get("password")

    if not email or not password:
        raise exceptions.BadRequest("Email and password are required", "missing_fields")

    user = await authTools.get_user_by_email(email, bypassCache=True, raw=True)

    if not user or not authTools.check_password(password, user["passwordHash"]):
        raise exceptions.BadRequest("Invalid email or password", "invalid_credentials")

    if user.get("status") == "blocked":
        raise exceptions.Forbidden("User is blocked.", "user_blocked")

    token = authTools.create_token(email)
    return {"success": True, "token": token}


@router.delete("/v2/accounts/delete", status_code=200)
@authRequired
async def v2_deleteAccount(request: Request):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    password = body.get("password")

    if not password:
        raise exceptions.BadRequest("Password is required", "missing_fields")

    rawUser = await authTools.get_user_by_email(request.state.user["email"], bypassCache=True, raw=True)

    if not authTools.check_password(password, rawUser["passwordHash"]):
        raise exceptions.BadRequest("Invalid password", "invalid_password")

    await authTools.delete_user(request.state.user)
    
    return {"success": True, "message": "Account deleted successfully"}