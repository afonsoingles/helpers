from fastapi import APIRouter, Request, BackgroundTasks
from api.utils.authTools import AuthenticationTools
from api.utils.notificationTools import NotificationTools
from api.decorators.auth import authRequired
import api.errors.exceptions as exceptions
from utils.systemTools import SystemTools
from utils.queueTools import QueueTools
from main import logger
import croniter
import datetime
import pytz



router = APIRouter()
authTools = AuthenticationTools()
notificationTools = NotificationTools()
systemTools = SystemTools()
queueTools = QueueTools(logger)

@router.get("/v2/helpers")
@authRequired
async def getAvailableHelpers(request: Request):

    availableHelpers = []

    helpers = await systemTools.get_all_helpers()
    for helper in helpers:
        if helper["internal"] or helper["disabled"] and not request.state.user["admin"]:
            continue
        if helper["admin_only"] and not request.state.user["admin"] and not request.state.impersonatedBy:
            continue
        
        availableHelpers.append(helper)
    return {"success": True, "message": "Helpers fetched successfully", "helpers": availableHelpers}

@router.post("/v2/helpers")
@authRequired
async def registerHelper(request: Request, backgroundTasks: BackgroundTasks):

    try:
        json = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")
    
    # param check - id
    registeredHelper = await systemTools.get_registered_helper(json.get("id"))
    if "id" not in json or not registeredHelper:
        raise exceptions.BadRequest("Invalid helper ID provided", "invalid_helper_id")
    
    if registeredHelper["internal"] == True or registeredHelper["disabled"] == True:
        raise exceptions.NotFound("This helper does not exist", "helper_not_found")
    
    if registeredHelper["admin_only"] == True and not request.state.user["admin"]: # do not allow impersonation bc admin_only is for running admin helpers
        raise exceptions.Forbidden("You are not authorized perform this action", "admin_required")
    
    if registeredHelper["require_admin_activation"] == True and not request.state.user["admin"] and not request.state.impersonatedBy: # allow impersonation so admins can activate helepers for users
        raise exceptions.Forbidden("You are not authorized perform this action", "admin_required")
    


    # param checks
    helperParams = {}
    for param, paramType in registeredHelper["params"].items():
        if param not in json:
            raise exceptions.BadRequest(f"Missing required parameters", "missing_parameters")
        if paramType == "str":
            try:
                json[param] = str(json[param])
            except:
                raise exceptions.BadRequest(f"Parameter {param} must be a string", "invalid_parameter_type")
        if paramType == "int":
            try:
                json[param] = int(json[param])
            except:
                raise exceptions.BadRequest(f"Parameter {param} must be an integer", "invalid_parameter_type")
        if paramType == "bool":
            try:
                json[param] = bool(json[param])
            except:
                raise exceptions.BadRequest(f"Parameter {param} must be a boolean", "invalid_parameter_type")
        helperParams[param] = json[param]
    
    if registeredHelper["allow_execution_time_config"] and not json.get("schedule"):
        raise exceptions.BadRequest("Missing required parameters", "missing_parameters")
    
    if registeredHelper["allow_execution_time_config"]: # cron expression validation
        existingSchedules = []
        for schedule in json["schedule"]:
            if schedule in existingSchedules:
                raise exceptions.BadRequest(f"Duplicate schedule expression '{schedule}'", "duplicate_schedule_expression")
            try:
                croniter.croniter(schedule, datetime.datetime.now(pytz.UTC)) # check if is valid
            except:
                raise exceptions.BadRequest(f"Invalid cron expression '{schedule}'", "invalid_cron_expression")
            
            existingSchedules.append(schedule)
            
    
    for helper in request.state.user["services"]:
        if helper["id"] == json["id"] and helper["enabled"] == True:
            raise exceptions.Conflict("Helper already registered", "helper_already_registered")
    
    helperData = {
        "id": json["id"],
        "enabled": True,
        "params": helperParams,
        "schedule": json["schedule"] if registeredHelper["allow_execution_time_config"] else [],
    }

    request.state.user["services"].append(helperData)
    await authTools.update_user(request.state.user["id"], request.state.user)
    
    backgroundTasks.add_task(queueTools.update_queue_for_user, user_id=request.state.user["id"])
    return {"success": True, "message": "Helper registered successfully!", "helper": helperData}

@router.delete("/v2/helpers/{helperId}")
@authRequired
async def unregisterHelper(request: Request, helperId: str, backgroundTasks: BackgroundTasks):
    registeredHelper = await systemTools.get_registered_helper(helperId)
    if not registeredHelper:
        raise exceptions.NotFound("This helper does not exist", "helper_not_found")
    
    if registeredHelper["internal"] == True:
        raise exceptions.NotFound("This helper does not exist", "helper_not_found")
    
    if registeredHelper["admin_only"] == True and not request.state.user["admin"]: 
        raise exceptions.Forbidden("You are not authorized perform this action", "admin_required")
    
    helperInUser = next((service for service in request.state.user["services"] if service["id"] == helperId), None)

    if not helperInUser:
        raise exceptions.NotFound("You do not have this helper registered", "helper_not_registered")
    request.state.user["services"] = [service for service in request.state.user["services"] if service["id"] != helperId]

    await authTools.update_user(request.state.user["id"], request.state.user)
    backgroundTasks.add_task(queueTools.update_queue_for_user, user_id=request.state.user["id"])

    return {"success": True, "message": "Helper unregistered successfully!"}


@router.put("/v2/helpers/{helperId}")
@authRequired
async def updateHelper(request: Request, helperId: str, backgroundTasks: BackgroundTasks):
    try:
        json = await request.json()
    except:
        raise exceptions.BadRequest("Invalid JSON data provided", "invalid_json")
    
    registeredHelper = await systemTools.get_registered_helper(helperId)
    if not registeredHelper:
        raise exceptions.NotFound("This helper does not exist", "helper_not_found")
    
    if registeredHelper["internal"] == True:
        raise exceptions.NotFound("This helper does not exist", "helper_not_found")
    
    if registeredHelper["admin_only"] == True and not request.state.user["admin"]: 
        raise exceptions.Forbidden("You are not authorized perform this action", "admin_required")
    
    helperInUser = next((service for service in request.state.user["services"] if service["id"] == helperId), None)

    if not helperInUser:
        raise exceptions.NotFound("You do not have this helper registered", "helper_not_registered")
    
    # param checks
    helperParams = helperInUser["params"]  
    for param, paramType in registeredHelper["params"].items():
        if param in json:  # Only update provided params
            if paramType == "str" and not isinstance(json[param], str):
                raise exceptions.BadRequest(f"Parameter {param} must be a string", "invalid_parameter_type")
            if paramType == "int" and not isinstance(json[param], int):
                raise exceptions.BadRequest(f"Parameter {param} must be an integer", "invalid_parameter_type")
            if paramType == "bool" and not isinstance(json[param], bool):
                raise exceptions.BadRequest(f"Parameter {param} must be a boolean", "invalid_parameter_type")
            helperParams[param] = json[param]
    

    if not registeredHelper["allow_execution_time_config"] and json.get("schedule"):
        raise exceptions.BadRequest("This helper does not support custom scheduling", "scheduling_not_supported")
    
    if registeredHelper["allow_execution_time_config"] and "schedule" in json: # cron expression validation
        existingSchedules = []
        for schedule in json["schedule"]:
            if schedule in existingSchedules:
                raise exceptions.BadRequest(f"Duplicate schedule expression '{schedule}'", "duplicate_schedule_expression")
            try:
                croniter.croniter(schedule, datetime.datetime.now(pytz.UTC)) # check if is valid
            except:
                raise exceptions.BadRequest(f"Invalid cron expression '{schedule}'", "invalid_cron_expression")
            
            existingSchedules.append(schedule)

        helperInUser["schedule"] = existingSchedules

    helperInUser["params"] = helperParams
    if "enabled" in json:
        if not isinstance(json["enabled"], bool):
            raise exceptions.BadRequest("Parameter 'enabled' must be a boolean", "invalid_parameter_type")
        helperInUser["enabled"] = json["enabled"]

    await authTools.update_user(request.state.user["id"], request.state.user)    
    backgroundTasks.add_task(queueTools.update_queue_for_user, user_id=request.state.user["id"])

    return {"success": True, "message": "Helper updated successfully!", "helper": helperInUser}    
    