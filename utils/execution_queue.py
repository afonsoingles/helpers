import asyncio
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from api.utils.redis import redisClient
import logging

logger = logging.getLogger("main")

class ExecutionQueue:
    """
    Redis-based execution queue system for helper scheduling.
    
    Implements the flow system described in the problem statement:
    - Priority queue temporal (Redis ZSET) ordered by executionTime and priority
    - 2-hour sliding window for queue management
    - Job status tracking and history
    """
    
    def __init__(self):
        self.AVAILABLE_HELPERS_KEY = "internalAvailableHelpers"
        self.EXECUTION_QUEUE_KEY = "internalExecutionQueue"
        self.EXECUTION_HISTORY_KEY = "internalExecutionHistory"
        self.EXECUTION_STATS_KEY = "internalExecutionStats"
        
        # Queue configuration
        self.LOOKAHEAD_HOURS = 2
        self.EXPANSION_INTERVAL_MINUTES = 5
        self.HISTORY_RETENTION_HOURS = 24
        
    async def register_helper(self, helper_name: str, helper_info: Dict) -> None:
        """Register a helper in the available helpers catalog."""
        await redisClient.hset(
            self.AVAILABLE_HELPERS_KEY,
            helper_name,
            json.dumps(helper_info)
        )
        logger.info(f"[QUEUE] Registered helper: {helper_name}")
    
    async def get_available_helpers(self) -> Dict[str, Dict]:
        """Get all available helpers from Redis."""
        helpers_data = await redisClient.hgetall(self.AVAILABLE_HELPERS_KEY)
        return {
            name: json.loads(data) 
            for name, data in helpers_data.items()
        }
    
    async def generate_execution_id(self) -> str:
        """Generate a unique execution ID."""
        return str(uuid.uuid4())
    
    async def create_execution(
        self, 
        user_id: str, 
        helper_name: str, 
        execution_time: datetime,
        priority: int = 3,
        execution_expiry: int = 300  # 5 minutes default
    ) -> str:
        """
        Create a new execution and add it to the queue.
        
        Args:
            user_id: User ID for the execution
            helper_name: Name of the helper to execute
            execution_time: When to execute (datetime)
            priority: Priority 1-5 (1 = highest priority)
            execution_expiry: Expiry time in seconds after execution_time
        
        Returns:
            execution_id: Unique identifier for the execution
        """
        execution_id = await self.generate_execution_id()
        execution_timestamp = int(execution_time.timestamp())
        
        # Create execution metadata
        execution_data = {
            "executionId": execution_id,
            "userId": user_id,
            "helper": helper_name,
            "executionTime": execution_timestamp,
            "priority": priority,
            "executionExpiry": execution_expiry,
            "status": "queued",
            "createdAt": int(datetime.now().timestamp())
        }
        
        # Store execution metadata
        await redisClient.hset(
            f"execution:{execution_id}",
            mapping=execution_data
        )
        
        # Add to priority queue (ZSET)
        # Score = execution_time + (priority * 0.0001) for secondary sorting
        score = execution_timestamp + (priority * 0.0001)
        await redisClient.zadd(
            self.EXECUTION_QUEUE_KEY,
            {execution_id: score}
        )
        
        logger.debug(f"[QUEUE] Created execution {execution_id} for {helper_name} at {execution_time}")
        return execution_id
    
    async def get_pending_executions(self, max_time: Optional[datetime] = None) -> List[Dict]:
        """
        Get executions that are ready to run (executionTime <= now).
        
        Args:
            max_time: Maximum execution time to consider (defaults to now)
        
        Returns:
            List of execution dictionaries ready for execution
        """
        if max_time is None:
            max_time = datetime.now()
        
        max_score = int(max_time.timestamp()) + 5  # Add 5 for priority buffer
        
        # Get execution IDs from queue
        execution_ids = await redisClient.zrangebyscore(
            self.EXECUTION_QUEUE_KEY,
            min=0,
            max=max_score
        )
        
        executions = []
        for execution_id in execution_ids:
            execution_data = await redisClient.hgetall(f"execution:{execution_id}")
            if execution_data and execution_data.get("status") == "queued":
                executions.append(execution_data)
        
        return executions
    
    async def update_execution_status(
        self, 
        execution_id: str, 
        status: str, 
        result: Optional[Dict] = None
    ) -> None:
        """Update the status of an execution."""
        update_data = {
            "status": status,
            "updatedAt": int(datetime.now().timestamp())
        }
        
        if result:
            update_data["result"] = json.dumps(result)
        
        await redisClient.hset(f"execution:{execution_id}", mapping=update_data)
        
        # If execution is completed or expired, remove from queue
        if status in ["success", "error", "expired"]:
            await redisClient.zrem(self.EXECUTION_QUEUE_KEY, execution_id)
            
            # Add to history for auditing
            await redisClient.zadd(
                self.EXECUTION_HISTORY_KEY,
                {execution_id: int(datetime.now().timestamp())}
            )
        
        logger.debug(f"[QUEUE] Updated execution {execution_id} status to {status}")
    
    async def check_expired_executions(self) -> List[str]:
        """Check for expired executions and mark them as expired."""
        now = datetime.now()
        current_timestamp = int(now.timestamp())
        
        # Get all queued executions
        execution_ids = await redisClient.zrange(self.EXECUTION_QUEUE_KEY, 0, -1)
        expired_executions = []
        
        for execution_id in execution_ids:
            execution_data = await redisClient.hgetall(f"execution:{execution_id}")
            if not execution_data or execution_data.get("status") != "queued":
                continue
            
            execution_time = int(execution_data.get("executionTime", 0))
            execution_expiry = int(execution_data.get("executionExpiry", 300))
            
            # Check if execution has expired
            if current_timestamp > execution_time + execution_expiry:
                await self.update_execution_status(execution_id, "expired")
                expired_executions.append(execution_id)
        
        if expired_executions:
            logger.info(f"[QUEUE] Marked {len(expired_executions)} executions as expired")
        
        return expired_executions
    
    async def generate_helper_executions(
        self, 
        helper_name: str, 
        helper_schedule: Dict,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[str]:
        """
        Generate executions for a helper based on its schedule configuration.
        
        Args:
            helper_name: Name of the helper
            helper_schedule: Schedule configuration (cron-like or interval)
            user_id: User ID for the executions
            start_time: Start time for generation
            end_time: End time for generation
        
        Returns:
            List of execution IDs created
        """
        execution_ids = []
        
        # Handle different schedule types
        schedule_type = helper_schedule.get("type")
        
        if schedule_type == "daily":
            # Daily schedule at specific time
            time_str = helper_schedule.get("time", "08:00:00")
            hour, minute, second = map(int, time_str.split(":"))
            
            current_date = start_time.date()
            while current_date <= end_time.date():
                execution_time = datetime.combine(current_date, datetime.min.time().replace(
                    hour=hour, minute=minute, second=second
                ))
                
                if start_time <= execution_time <= end_time:
                    execution_id = await self.create_execution(
                        user_id=user_id,
                        helper_name=helper_name,
                        execution_time=execution_time,
                        priority=helper_schedule.get("priority", 3),
                        execution_expiry=helper_schedule.get("expiry", 300)
                    )
                    execution_ids.append(execution_id)
                
                current_date += timedelta(days=1)
        
        elif schedule_type == "interval":
            # Interval-based schedule
            interval_minutes = helper_schedule.get("interval_minutes", 60)
            interval = timedelta(minutes=interval_minutes)
            
            current_time = start_time
            while current_time <= end_time:
                execution_id = await self.create_execution(
                    user_id=user_id,
                    helper_name=helper_name,
                    execution_time=current_time,
                    priority=helper_schedule.get("priority", 3),
                    execution_expiry=helper_schedule.get("expiry", 300)
                )
                execution_ids.append(execution_id)
                current_time += interval
        
        logger.info(f"[QUEUE] Generated {len(execution_ids)} executions for {helper_name}")
        return execution_ids
    
    async def build_initial_queue(self, active_helpers: Dict[str, Dict]) -> None:
        """
        Build the initial 2-hour execution queue for all active helpers.
        
        Args:
            active_helpers: Dictionary of helper_name -> helper_config
        """
        now = datetime.now()
        end_time = now + timedelta(hours=self.LOOKAHEAD_HOURS)
        
        logger.info(f"[QUEUE] Building initial queue from {now} to {end_time}")
        
        total_executions = 0
        for helper_name, helper_config in active_helpers.items():
            schedule_config = helper_config.get("schedule", {})
            if not schedule_config:
                continue
            
            # For now, assume user_id = "system" for global helpers
            # In a real implementation, this would iterate through active users
            user_id = "system"
            
            execution_ids = await self.generate_helper_executions(
                helper_name=helper_name,
                helper_schedule=schedule_config,
                user_id=user_id,
                start_time=now,
                end_time=end_time
            )
            total_executions += len(execution_ids)
        
        logger.info(f"[QUEUE] Built initial queue with {total_executions} executions")
    
    async def expand_queue_window(self, active_helpers: Dict[str, Dict]) -> None:
        """
        Expand the queue by 5 minutes while maintaining 2-hour lookahead.
        This should be called every 5 minutes.
        """
        now = datetime.now()
        # Calculate the new window end time
        new_end_time = now + timedelta(hours=self.LOOKAHEAD_HOURS)
        expansion_start = new_end_time - timedelta(minutes=self.EXPANSION_INTERVAL_MINUTES)
        
        logger.debug(f"[QUEUE] Expanding queue window from {expansion_start} to {new_end_time}")
        
        total_executions = 0
        for helper_name, helper_config in active_helpers.items():
            schedule_config = helper_config.get("schedule", {})
            if not schedule_config:
                continue
            
            user_id = "system"  # System-level helpers
            
            execution_ids = await self.generate_helper_executions(
                helper_name=helper_name,
                helper_schedule=schedule_config,
                user_id=user_id,
                start_time=expansion_start,
                end_time=new_end_time
            )
            total_executions += len(execution_ids)
        
        logger.debug(f"[QUEUE] Expanded queue with {total_executions} new executions")
    
    async def cleanup_old_history(self) -> None:
        """Remove executions older than 24 hours from history."""
        cutoff_time = int((datetime.now() - timedelta(hours=self.HISTORY_RETENTION_HOURS)).timestamp())
        
        # Remove old execution histories
        removed = await redisClient.zremrangebyscore(
            self.EXECUTION_HISTORY_KEY,
            min=0,
            max=cutoff_time
        )
        
        if removed > 0:
            logger.debug(f"[QUEUE] Cleaned up {removed} old execution histories")
    
    async def get_helper_status(self, helper_name: str) -> Dict:
        """Get status information for a specific helper."""
        # Count queued executions
        execution_ids = await redisClient.zrange(self.EXECUTION_QUEUE_KEY, 0, -1)
        queued_count = 0
        
        for execution_id in execution_ids:
            execution_data = await redisClient.hgetall(f"execution:{execution_id}")
            if execution_data.get("helper") == helper_name and execution_data.get("status") == "queued":
                queued_count += 1
        
        return {
            "helper_name": helper_name,
            "queued_executions": queued_count,
            "is_registered": await redisClient.hexists(self.AVAILABLE_HELPERS_KEY, helper_name)
        }