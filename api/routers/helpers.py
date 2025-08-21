from fastapi import APIRouter, HTTPException, Depends
from api.decorators.auth import require_admin
from utils.execution_queue import ExecutionQueue
from utils.execution_dispatcher import ExecutionDispatcher
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger("main")

router = APIRouter(prefix="/helpers", tags=["helpers"])

# Global instances (will be initialized by main application)
execution_queue: Optional[ExecutionQueue] = None
execution_dispatcher: Optional[ExecutionDispatcher] = None

def init_helper_management(queue: ExecutionQueue, dispatcher: ExecutionDispatcher):
    """Initialize the helper management system with queue and dispatcher instances."""
    global execution_queue, execution_dispatcher
    execution_queue = queue
    execution_dispatcher = dispatcher

class HelperScheduleConfig(BaseModel):
    type: str  # "daily", "interval", "cron"
    time: Optional[str] = None  # For daily: "HH:MM:SS"
    interval_minutes: Optional[int] = None  # For interval
    cron: Optional[str] = None  # For cron
    priority: int = 3  # 1-5
    expiry: int = 300  # seconds
    enabled: bool = True

class HelperUpdateRequest(BaseModel):
    schedule: Optional[HelperScheduleConfig] = None
    enabled: Optional[bool] = None

@router.get("/")
async def list_helpers():
    """Get list of all available helpers."""
    if not execution_queue:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        helpers = await execution_queue.get_available_helpers()
        return {
            "helpers": helpers,
            "count": len(helpers)
        }
    except Exception as e:
        logger.error(f"[API] Error listing helpers: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve helpers")

@router.get("/{helper_name}")
async def get_helper_details(helper_name: str):
    """Get detailed information about a specific helper."""
    if not execution_queue:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        helpers = await execution_queue.get_available_helpers()
        
        if helper_name not in helpers:
            raise HTTPException(status_code=404, detail=f"Helper {helper_name} not found")
        
        helper_info = helpers[helper_name]
        helper_status = await execution_queue.get_helper_status(helper_name)
        
        return {
            "helper": helper_info,
            "status": helper_status
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error getting helper details for {helper_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve helper details")

@router.post("/{helper_name}/enable")
async def enable_helper(helper_name: str, admin=Depends(require_admin)):
    """
    Enable a helper - generates executions until the current queue window limit.
    """
    if not execution_queue:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        helpers = await execution_queue.get_available_helpers()
        
        if helper_name not in helpers:
            raise HTTPException(status_code=404, detail=f"Helper {helper_name} not found")
        
        helper_info = helpers[helper_name]
        
        # Update helper as enabled
        helper_info["schedule"]["enabled"] = True
        await execution_queue.register_helper(helper_name, helper_info)
        
        # Generate executions for the current window
        from datetime import datetime, timedelta
        now = datetime.now()
        end_time = now + timedelta(hours=execution_queue.LOOKAHEAD_HOURS)
        
        execution_ids = await execution_queue.generate_helper_executions(
            helper_name=helper_name,
            helper_schedule=helper_info["schedule"],
            user_id="system",
            start_time=now,
            end_time=end_time
        )
        
        logger.info(f"[API] Enabled helper {helper_name}, generated {len(execution_ids)} executions")
        
        return {
            "message": f"Helper {helper_name} enabled successfully",
            "executions_generated": len(execution_ids),
            "execution_ids": execution_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error enabling helper {helper_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enable helper")

@router.post("/{helper_name}/disable")
async def disable_helper(helper_name: str, admin=Depends(require_admin)):
    """
    Disable a helper - removes future executions but keeps historical data.
    """
    if not execution_queue:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        helpers = await execution_queue.get_available_helpers()
        
        if helper_name not in helpers:
            raise HTTPException(status_code=404, detail=f"Helper {helper_name} not found")
        
        helper_info = helpers[helper_name]
        
        # Update helper as disabled
        helper_info["schedule"]["enabled"] = False
        await execution_queue.register_helper(helper_name, helper_info)
        
        # Remove future executions for this helper
        from api.utils.redis import redisClient
        execution_ids = await redisClient.zrange(execution_queue.EXECUTION_QUEUE_KEY, 0, -1)
        removed_count = 0
        
        for execution_id in execution_ids:
            execution_data = await redisClient.hgetall(f"execution:{execution_id}")
            if execution_data.get("helper") == helper_name and execution_data.get("status") == "queued":
                await redisClient.zrem(execution_queue.EXECUTION_QUEUE_KEY, execution_id)
                await redisClient.delete(f"execution:{execution_id}")
                removed_count += 1
        
        logger.info(f"[API] Disabled helper {helper_name}, removed {removed_count} future executions")
        
        return {
            "message": f"Helper {helper_name} disabled successfully",
            "executions_removed": removed_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error disabling helper {helper_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable helper")

@router.put("/{helper_name}")
async def update_helper(helper_name: str, update_request: HelperUpdateRequest, admin=Depends(require_admin)):
    """
    Update helper configuration - removes old executions and generates new ones.
    """
    if not execution_queue:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        helpers = await execution_queue.get_available_helpers()
        
        if helper_name not in helpers:
            raise HTTPException(status_code=404, detail=f"Helper {helper_name} not found")
        
        helper_info = helpers[helper_name]
        
        # Update configuration
        if update_request.schedule:
            helper_info["schedule"] = update_request.schedule.dict()
        
        if update_request.enabled is not None:
            helper_info["schedule"]["enabled"] = update_request.enabled
        
        # Remove old executions
        from api.utils.redis import redisClient
        execution_ids = await redisClient.zrange(execution_queue.EXECUTION_QUEUE_KEY, 0, -1)
        removed_count = 0
        
        for execution_id in execution_ids:
            execution_data = await redisClient.hgetall(f"execution:{execution_id}")
            if execution_data.get("helper") == helper_name and execution_data.get("status") == "queued":
                await redisClient.zrem(execution_queue.EXECUTION_QUEUE_KEY, execution_id)
                await redisClient.delete(f"execution:{execution_id}")
                removed_count += 1
        
        # Update helper in Redis
        await execution_queue.register_helper(helper_name, helper_info)
        
        # Generate new executions if enabled
        execution_ids = []
        if helper_info["schedule"]["enabled"]:
            from datetime import datetime, timedelta
            now = datetime.now()
            end_time = now + timedelta(hours=execution_queue.LOOKAHEAD_HOURS)
            
            execution_ids = await execution_queue.generate_helper_executions(
                helper_name=helper_name,
                helper_schedule=helper_info["schedule"],
                user_id="system",
                start_time=now,
                end_time=end_time
            )
        
        logger.info(f"[API] Updated helper {helper_name}, removed {removed_count} old executions, generated {len(execution_ids)} new executions")
        
        return {
            "message": f"Helper {helper_name} updated successfully",
            "executions_removed": removed_count,
            "executions_generated": len(execution_ids),
            "helper_config": helper_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error updating helper {helper_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update helper")

@router.get("/status/system")
async def get_system_status():
    """Get overall system status for the helper execution system."""
    if not execution_queue or not execution_dispatcher:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        # Get queue status
        available_helpers = await execution_queue.get_available_helpers()
        
        # Get dispatcher status
        dispatcher_status = await execution_dispatcher.get_status()
        
        # Count queued executions
        from api.utils.redis import redisClient
        total_queued = await redisClient.zcard(execution_queue.EXECUTION_QUEUE_KEY)
        
        return {
            "system_status": "operational",
            "available_helpers": len(available_helpers),
            "total_queued_executions": total_queued,
            "dispatcher": dispatcher_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[API] Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")

@router.get("/executions/queue")
async def get_execution_queue(limit: int = 50):
    """Get current execution queue (for monitoring/debugging)."""
    if not execution_queue:
        raise HTTPException(status_code=503, detail="Helper management system not initialized")
    
    try:
        from api.utils.redis import redisClient
        
        # Get execution IDs from queue (limited)
        execution_ids = await redisClient.zrange(
            execution_queue.EXECUTION_QUEUE_KEY, 
            0, 
            limit - 1, 
            withscores=True
        )
        
        executions = []
        for execution_id, score in execution_ids:
            execution_data = await redisClient.hgetall(f"execution:{execution_id}")
            if execution_data:
                execution_data["queue_score"] = score
                executions.append(execution_data)
        
        return {
            "executions": executions,
            "count": len(executions),
            "total_in_queue": await redisClient.zcard(execution_queue.EXECUTION_QUEUE_KEY)
        }
        
    except Exception as e:
        logger.error(f"[API] Error getting execution queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve execution queue")