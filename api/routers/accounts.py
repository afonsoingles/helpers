import os
from fastapi import APIRouter, Request
import api.errors.exceptions as exceptions
from api.utils.authTools import AuthenticationTools
from utils.mailer import Mailer
from api.decorators.auth import authRequired
from datetime import datetime
import pytz


router = APIRouter()
authTools = AuthenticationTools()
mailer = Mailer()




@router.get("/v2/accounts/me", status_code=200)
@router.get("/v1/accounts/me", status_code=200)
@authRequired(allowBanned=True)
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


# Admin account management

@router.get("/v2/admin/users", status_code=200)
@authRequired(admin=True)
async def v2_admin_listUsers(request: Request, page: int = 1, limit: int = 10, search: str = None):

    users = await authTools.get_paginated_users(page=page, limit=limit, search=search)
    return {"success": True, "users": users}


@router.get("/v2/users/{userId}", status_code=200)
@authRequired(admin=True)
async def v2_admin_getUser(request: Request, userId: str):
    user = await authTools.get_user_by_id(userId)
    if not user:
        raise exceptions.NotFound("User not found", "user_not_found")
    return {"success": True, "user": user}


@router.put("/users/{userId}", status_code=200)
@authRequired(admin=True)
async def v2_admin_editUser(request: Request, userId: str):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    existing_user = await authTools.get_user_by_id(userId)
    if not existing_user:
        raise exceptions.NotFound("User not found", "user_not_found")

    updated_data = {**existing_user, **{k: v for k, v in body.items() if v is not None}}

    updated_user = await authTools.update_user(userId, updated_data)

    return {"success": True, "message": "User details updated successfully", "user": updated_user}


@router.post("/users/{userId}/block", status_code=200)
@authRequired(admin=True)
async def v2_admin_blockUser(request: Request, userId: str):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    reason = body.get("reason")
    if not reason:
        raise exceptions.BadRequest("Reason is required", "missing_reason")

    blocked_user = await authTools.block_user(userId, reason)

    mailer.send_email(
        sender="Helpers",
        subject="Account Blocked",
        templateName="suspended",
        to=blocked_user["email"],
        userName=blocked_user["name"],
        note=reason

    )
    if not blocked_user:
        raise exceptions.NotFound("User not found", "user_not_found")
    return {"success": True, "message": "User blocked successfully", "user": blocked_user}


@router.post("/users/{userId}/unblock", status_code=200)
@authRequired(admin=True)
async def v2_admin_unblockUser(request: Request, userId: str):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    reason = body.get("reason")
    if not reason:
        raise exceptions.BadRequest("Reason is required", "missing_reason")

    unblocked_user = await authTools.unblock_user(userId, reason)
    if not unblocked_user:
        raise exceptions.NotFound("User not found", "user_not_found")
    return {"success": True, "message": "User unblocked successfully", "user": unblocked_user}


@router.post("/users/{userId}/reset-password", status_code=200)
@authRequired(admin=True)
async def v2_resetPassword(request: Request, userId: str):
    try:
        body = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")

    new_password = body.get("new_password")
    if not new_password:
        raise exceptions.BadRequest("New password is required", "missing_password")

    updated_user = await authTools.reset_password(userId, new_password)
    if not updated_user:
        raise exceptions.NotFound("User not found", "user_not_found")
    return {"success": True, "message": "Password reset successfully", "user": updated_user}