import os
from fastapi import APIRouter, Request
import api.errors.exceptions as exceptions
from api.utils.authTools import AuthenticationTools
from api.decorators.auth import authRequired
from datetime import datetime
import pytz


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


@router.post("v2/accounts/signup")
async def v2_signup(request: Request):
    body = await request.json()

    currentTime = datetime.now(pytz.timezone(os.environ.get("TIMEZONE")))

    userData = {
        "name": body.get("name"),
        "username": body.get("username"),
        "email": body.get("email"),
        "passwordHash": authTools.hash_password(body.get("password")),
        "status": "active",
        "timezone": body.get("timezone", os.environ.get("TIMEZONE")),
        "pushConfiguration": [],
        "services": [],
        "createdAt": int(currentTime.timestamp()),
        "updatedAt": int(currentTime.timestamp()),
    }

    if not userData["name"] or not userData["username"] or not userData["email"] or not userData["passwordHash"]:
        raise exceptions.BadRequest("All fields are required", "missing_fields")
    
    if authTools.get_user_by_email(userData["email"]):
        raise exceptions.BadRequest("This email is already registered", "email_taken")

    if authTools.get_user_by_username(userData["username"]):
        raise exceptions.BadRequest("This username is already taken", "username_taken")
    
    authTools.create_user(userData)
    
    return {"success": True, "message": "User created successfully. You can now log in."}