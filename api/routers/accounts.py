import os
from fastapi import APIRouter, Request
import api.errors.exceptions as exceptions
from api.utils.authTools import AuthenticationTools
from utils.mailer import Mailer
from api.decorators.auth import authRequired
from api.utils.ipData import IPData
from datetime import datetime
import pytz


router = APIRouter()
authTools = AuthenticationTools()
mailer = Mailer()
ipData = IPData()




@router.get("/v2/accounts/me", status_code=200)
@router.get("/v1/accounts/me", status_code=200)
@authRequired(allowBanned=True)
async def me(request: Request):
    if not request.state.user.get("region"):
        userIp = await ipData.get_ip_data(request.client.host)
        request.state.user["region"] = userIp["country_code"]
        await authTools.update_user(request.state.user["id"], request.state.user)

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
        "status": "" ,
        "timezone": body.get("timezone", os.environ.get("TIMEZONE")),
        "region": "",
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
    
    userIp = await ipData.get_ip_data(request.client.host)
    if userIp.get("threat"):
        if userIp["threat"]["is_tor"] or userIp["threat"]["is_datacenter"] or userIp["threat"]["is_anonymous"] or userIp["threat"]["is_known_attacker"] or userIp["threat"]["is_known_abuser"] or userIp["threat"]["is_threat"] or userIp["threat"]["is_bogon"]:
            abuseFlag = True

        if userIp["threat"]["threat_score"] >= 55 or userIp["trust_score"] <= 40:
            abuseFlag = True
    else:
        abuseFlag = False
    
    userData["region"] = userIp["country_code"]
    userData["status"] = "suspended" if abuseFlag else "active"


    await authTools.create_user(userData)
    
    if abuseFlag:
        mailer.send_email(
            sender="Helpers",
            subject="Your account has been flagged",
            templateName="abuse_detected",
            to=userData["email"],
            userName=userData["name"]
        )
        raise exceptions.Forbidden("Your account has been flagged. Please contact support", "account_flagged")
    
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


@router.delete("/v2/accounts/delete", status_code=200) # NOTE: this requires admin impersonation to confirm delete
@authRequired(allowBanned=True)
async def v2_deleteAccount(request: Request):

    if request.state.user.get("status") == "deletionPending" and not request.state.impersonatedBy:
        raise exceptions.Forbidden("Your account is already pending deletion. Please wait for the process to complete.", "deletion_pending")

    if request.state.user.get("status") == "deletionPending" and request.state.impersonatedBy:

        await authTools.delete_user(request.state.user)
        mailer.send_email(
            sender="Helpers",
            subject="Your account has been deleted",
            templateName="account_deleted",
            to=request.state.user["email"],
            userName=request.state.user["name"]
        )
        return {"success": True, "message": "Deletion confirmed. This account is now deleted."}
    
    request.state.user["status"] = "deletionPending"
    await authTools.update_user(request.state.user["id"], request.state.user)
    mailer.send_email(
        sender="Helpers",
        subject="Your account deletion is pending",
        templateName="account_pending_deletion",
        to=request.state.user["email"],
        userName=request.state.user["name"]
    )

    return {"success": True, "message": "Your account deletion is now pending"}


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
        subject="Your account was suspended",
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