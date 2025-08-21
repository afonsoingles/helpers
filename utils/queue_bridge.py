"""
Compatibility bridge for gradual migration to the new execution queue system.

This module allows the new queue system to work alongside the existing schedule-based system,
enabling a gradual migration without breaking existing functionality.
"""

import asyncio
import os
from utils.shared_logger import logger

# Global instances
queued_startup = None
queue_enabled = False

def init_queue_system():
    """Initialize the execution queue system if enabled."""
    global queued_startup, queue_enabled
    
    # Check if queue system is enabled via environment variable
    queue_enabled = os.environ.get("ENABLE_EXECUTION_QUEUE", "false").lower() == "true"
    
    if queue_enabled:
        logger.info("[BRIDGE] Execution queue system enabled")
        return True
    else:
        logger.info("[BRIDGE] Execution queue system disabled, using legacy scheduling")
        return False

async def start_queue_system():
    """Start the execution queue system if initialized."""
    global queued_startup, queue_enabled
    
    if not queue_enabled:
        return None
    
    if not queued_startup:
        # Lazy import to avoid Redis connection issues during import
        try:
            from utils.queued_startup import QueuedStartup
            queued_startup = QueuedStartup()
            logger.info("[BRIDGE] Created QueuedStartup instance")
        except Exception as e:
            logger.error(f"[BRIDGE] Failed to create QueuedStartup: {e}")
            return None
    
    if queued_startup:
        logger.info("[BRIDGE] Starting execution queue system")
        try:
            await queued_startup.startup_sequence()
            return queued_startup
        except Exception as e:
            logger.error(f"[BRIDGE] Failed to start execution queue system: {e}")
            return None
    
    return None

async def get_queue_status():
    """Get status of the queue system if running."""
    global queued_startup, queue_enabled
    
    if queue_enabled and queued_startup:
        try:
            return await queued_startup.get_system_status()
        except Exception as e:
            logger.error(f"[BRIDGE] Failed to get queue status: {e}")
            return {"error": str(e)}
    
    return {"queue_enabled": False, "message": "Queue system not enabled"}

def is_queue_enabled():
    """Check if the queue system is enabled."""
    return queue_enabled

def get_queued_startup():
    """Get the queued startup instance if available."""
    return queued_startup

def setup_api_integration():
    """Setup API integration for helper management if queue is enabled."""
    global queued_startup, queue_enabled
    
    if queue_enabled and queued_startup:
        try:
            from api.routers.helpers import init_helper_management
            init_helper_management(queued_startup.execution_queue, queued_startup.dispatcher)
            logger.info("[BRIDGE] API helper management integration setup complete")
            return True
        except Exception as e:
            logger.error(f"[BRIDGE] Failed to setup API integration: {e}")
            return False
    
    return False