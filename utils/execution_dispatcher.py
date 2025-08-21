import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from utils.execution_queue import ExecutionQueue
import importlib
import os
from bases.helper import BaseHelper

logger = logging.getLogger("main")

class ExecutionDispatcher:
    """
    Dispatcher that manages the execution of queued helper jobs.
    
    Implements the runtime cycle described in the problem statement:
    - Dispatcher loop (checks jobs every second)
    - Executes jobs that are ready
    - Handles job expiration
    - Manages sliding window queue expansion
    """
    
    def __init__(self, execution_queue: ExecutionQueue):
        self.queue = execution_queue
        self.helpers_registry = {}  # Cache of loaded helper instances
        self.running_tasks = {}  # Track currently running executions
        self.should_stop = False
        
        # Configuration
        self.DISPATCH_INTERVAL = 1  # Check for jobs every second
        self.QUEUE_EXPANSION_INTERVAL = 300  # Expand queue every 5 minutes
        
    async def register_helper_instance(self, helper_name: str, helper_instance: BaseHelper):
        """Register a helper instance for execution."""
        self.helpers_registry[helper_name] = helper_instance
        logger.info(f"[DISPATCHER] Registered helper instance: {helper_name}")
    
    async def load_helper_instances(self) -> Dict[str, BaseHelper]:
        """
        Load all helper instances from the helpers directory.
        Similar to the existing discover_helpers functionality.
        """
        helpers = {}
        
        if not os.path.exists("helpers"):
            logger.warning("[DISPATCHER] Helpers directory not found")
            return helpers
        
        helper_files = [file for file in os.listdir("helpers") if file.endswith('.py')]
        
        for file in helper_files:
            module_name = f"helpers.{file[:-3]}"
            try:
                module = importlib.import_module(module_name)
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, BaseHelper) and obj is not BaseHelper:
                        try:
                            helper_instance = obj()
                            helper_name = helper_instance.__class__.__name__
                            helpers[helper_name] = helper_instance
                            await self.register_helper_instance(helper_name, helper_instance)
                            logger.info(f"[DISPATCHER] Loaded helper: {helper_name}")
                        except Exception as e:
                            logger.error(f"[DISPATCHER] Error instantiating helper {obj.__name__}: {e}")
            except Exception as e:
                logger.error(f"[DISPATCHER] Error importing helper {module_name}: {e}")
        
        return helpers
    
    async def execute_helper(self, execution_data: Dict) -> Dict:
        """
        Execute a specific helper and return the result.
        
        Args:
            execution_data: Execution metadata from Redis
            
        Returns:
            Dict with execution result and metadata
        """
        execution_id = execution_data.get("executionId")
        helper_name = execution_data.get("helper")
        
        logger.info(f"[DISPATCHER] Executing {helper_name} (execution_id: {execution_id})")
        
        # Check if helper is registered
        if helper_name not in self.helpers_registry:
            error_msg = f"Helper {helper_name} not found in registry"
            logger.error(f"[DISPATCHER] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "execution_time": datetime.now().isoformat()
            }
        
        helper_instance = self.helpers_registry[helper_name]
        
        try:
            # Update execution status to running
            await self.queue.update_execution_status(execution_id, "running")
            
            # Execute the helper in a separate thread to avoid blocking
            start_time = datetime.now()
            await asyncio.to_thread(helper_instance.run)
            end_time = datetime.now()
            
            execution_duration = (end_time - start_time).total_seconds()
            
            result = {
                "success": True,
                "execution_time": start_time.isoformat(),
                "completion_time": end_time.isoformat(),
                "duration_seconds": execution_duration
            }
            
            # Update execution status to success
            await self.queue.update_execution_status(execution_id, "success", result)
            
            logger.info(f"[DISPATCHER] Successfully executed {helper_name} in {execution_duration:.2f}s")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            error_result = {
                "success": False,
                "error": str(e),
                "execution_time": start_time.isoformat() if 'start_time' in locals() else datetime.now().isoformat(),
                "completion_time": end_time.isoformat()
            }
            
            # Update execution status to error
            await self.queue.update_execution_status(execution_id, "error", error_result)
            
            logger.error(f"[DISPATCHER] Error executing {helper_name}: {e}")
            return error_result
    
    async def dispatch_pending_executions(self):
        """
        Check for pending executions and dispatch them.
        This is the core dispatcher loop logic.
        """
        try:
            # First, check for expired executions
            await self.queue.check_expired_executions()
            
            # Get pending executions
            pending_executions = await self.queue.get_pending_executions()
            
            for execution_data in pending_executions:
                execution_id = execution_data.get("executionId")
                
                # Skip if already running
                if execution_id in self.running_tasks:
                    continue
                
                # Create task for execution
                task = asyncio.create_task(
                    self.execute_helper(execution_data),
                    name=f"execute_{execution_id}"
                )
                self.running_tasks[execution_id] = task
                
                # Add callback to remove from running tasks when done
                def task_done_callback(task_ref, exec_id=execution_id):
                    if exec_id in self.running_tasks:
                        del self.running_tasks[exec_id]
                
                task.add_done_callback(lambda t, exec_id=execution_id: task_done_callback(t, exec_id))
                
        except Exception as e:
            logger.error(f"[DISPATCHER] Error in dispatch loop: {e}")
    
    async def queue_expansion_loop(self):
        """
        Periodic task to expand the execution queue every 5 minutes.
        """
        while not self.should_stop:
            try:
                await asyncio.sleep(self.QUEUE_EXPANSION_INTERVAL)
                
                # Get active helpers from Redis
                active_helpers = await self.queue.get_available_helpers()
                
                # Expand the queue
                await self.queue.expand_queue_window(active_helpers)
                
                # Cleanup old history
                await self.queue.cleanup_old_history()
                
            except Exception as e:
                logger.error(f"[DISPATCHER] Error in queue expansion loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    async def dispatcher_loop(self):
        """
        Main dispatcher loop that runs continuously.
        """
        logger.info("[DISPATCHER] Starting dispatcher loop")
        
        while not self.should_stop:
            try:
                await self.dispatch_pending_executions()
                await asyncio.sleep(self.DISPATCH_INTERVAL)
                
            except Exception as e:
                logger.error(f"[DISPATCHER] Error in main dispatcher loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def start(self):
        """Start the dispatcher with all its background tasks."""
        logger.info("[DISPATCHER] Starting execution dispatcher")
        
        # Load helper instances
        await self.load_helper_instances()
        
        # Start background tasks
        dispatcher_task = asyncio.create_task(self.dispatcher_loop())
        expansion_task = asyncio.create_task(self.queue_expansion_loop())
        
        return [dispatcher_task, expansion_task]
    
    async def stop(self):
        """Stop the dispatcher and cancel all running tasks."""
        logger.info("[DISPATCHER] Stopping execution dispatcher")
        self.should_stop = True
        
        # Cancel all running execution tasks
        for execution_id, task in self.running_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"[DISPATCHER] Cancelled running execution: {execution_id}")
        
        # Wait for tasks to finish
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
            
        self.running_tasks.clear()
    
    async def get_status(self) -> Dict:
        """Get current dispatcher status."""
        active_helpers = await self.queue.get_available_helpers()
        
        return {
            "registered_helpers": len(self.helpers_registry),
            "available_helpers": len(active_helpers),
            "running_executions": len(self.running_tasks),
            "dispatcher_running": not self.should_stop
        }