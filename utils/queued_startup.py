import asyncio
import logging
import os
import importlib
from datetime import datetime
from typing import Dict, List
from utils.execution_queue import ExecutionQueue
from utils.execution_dispatcher import ExecutionDispatcher
from bases.helper import BaseHelper
from utils.shared_logger import logger

class QueuedStartup:
    """
    New startup system that implements the execution queue flow.
    
    Replaces the legacy schedule-based system with Redis queue management.
    """
    
    def __init__(self):
        self.execution_queue = ExecutionQueue()
        self.dispatcher = ExecutionDispatcher(self.execution_queue)
        self.background_tasks = []
        
    def discover_helpers(self) -> List[BaseHelper]:
        """
        Discover helper classes from the helpers directory.
        Inlined version of the legacy startup helper discovery.
        """
        helpers = []

        if not os.path.exists("helpers"):
            logger.warning("[STARTUP] Helpers directory not found")
            return helpers

        helper_files = [file for file in os.listdir("helpers") if file.endswith('.py')]

        for file in helper_files:
            module_name = f"helpers.{file[:-3]}"
            try:
                module = importlib.import_module(module_name)
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, BaseHelper) and obj is not BaseHelper:
                        logger.info(f"[STARTUP] Loaded helper: {obj.__name__}")
                        helpers.append(obj())
            except Exception as e:
                logger.error(f"[STARTUP] Error importing helper {module_name}: {e}", e)
        
        return helpers
        
    async def register_available_helpers(self, helpers: List) -> Dict[str, Dict]:
        """
        Register all discovered helpers in Redis catalog.
        
        Args:
            helpers: List of helper instances
            
        Returns:
            Dict of helper_name -> helper_config
        """
        helper_configs = {}
        
        for helper in helpers:
            helper_name = helper.__class__.__name__
            
            # Get schedule configuration
            try:
                schedule_config = helper.get_schedule_config()
            except Exception as e:
                logger.warning(f"[STARTUP] Helper {helper_name} doesn't have get_schedule_config, using default: {e}")
                schedule_config = {
                    "type": "interval",
                    "interval_minutes": 60,
                    "priority": getattr(helper, 'priority', 3),
                    "expiry": getattr(helper, 'timeout', 300),
                    "enabled": True
                }
            
            # Build helper info
            helper_info = {
                "name": helper_name,
                "class_name": helper.__class__.__name__,
                "module": helper.__class__.__module__,
                "schedule": schedule_config,
                "boot_start": getattr(helper, 'boot_start', False),
                "priority": getattr(helper, 'priority', 3),
                "timeout": getattr(helper, 'timeout', 300),
                "internal": getattr(helper, 'internal', False),
                "admin_only": getattr(helper, 'admin_only', False),
                "registered_at": datetime.now().isoformat()
            }
            
            # Register in Redis
            await self.execution_queue.register_helper(helper_name, helper_info)
            helper_configs[helper_name] = helper_info
        
        logger.info(f"[STARTUP] Registered {len(helper_configs)} helpers in Redis catalog")
        return helper_configs
    
    async def run_boot_helpers(self, helpers: List):
        """
        Run helpers that should execute at startup (boot_start=True).
        """
        boot_helpers = [h for h in helpers if getattr(h, 'boot_start', False)]
        
        if not boot_helpers:
            logger.info("[STARTUP] No boot helpers to run")
            return
        
        logger.info(f"[STARTUP] Running {len(boot_helpers)} boot helpers")
        
        # Run boot helpers sequentially to avoid conflicts
        for helper in boot_helpers:
            try:
                helper_name = helper.__class__.__name__
                logger.info(f"[STARTUP] Running boot helper: {helper_name}")
                await asyncio.to_thread(helper.run)
                logger.info(f"[STARTUP] Boot helper {helper_name} completed successfully")
            except Exception as e:
                logger.error(f"[STARTUP] Error running boot helper {helper.__class__.__name__}: {e}")
    
    async def build_initial_execution_queue(self, helper_configs: Dict[str, Dict]):
        """
        Build the initial 2-hour execution queue for all active helpers.
        """
        logger.info("[STARTUP] Building initial execution queue")
        
        # Filter enabled helpers
        active_helpers = {
            name: config for name, config in helper_configs.items()
            if config.get("schedule", {}).get("enabled", True)
        }
        
        if not active_helpers:
            logger.warning("[STARTUP] No active helpers found for queue building")
            return
        
        # Build the queue
        await self.execution_queue.build_initial_queue(active_helpers)
        logger.info("[STARTUP] Initial execution queue built successfully")
    
    async def startup_sequence(self):
        """
        Execute the complete startup sequence as described in the problem statement.
        
        1. Register helpers in Redis
        2. Run boot helpers
        3. Build initial 2-hour execution queue
        4. Start dispatcher
        """
        logger.info("[STARTUP] Beginning queued startup sequence")
        
        # Step 1: Discover helpers (using inlined discovery)
        helpers = self.discover_helpers()
        logger.info(f"[STARTUP] Discovered {len(helpers)} helpers")
        
        # Step 2: Register helpers in Redis catalog
        helper_configs = await self.register_available_helpers(helpers)
        
        # Step 3: Run boot helpers
        await self.run_boot_helpers(helpers)
        
        # Step 4: Build initial execution queue
        await self.build_initial_execution_queue(helper_configs)
        
        # Step 5: Start the dispatcher
        dispatcher_tasks = await self.dispatcher.start()
        self.background_tasks.extend(dispatcher_tasks)
        
        logger.info("[STARTUP] Queued startup sequence completed successfully")
    
    async def start_api_server(self, api_config: Dict = None):
        """Start the API server (maintains compatibility with existing startup)."""
        if api_config is None:
            api_config = {
                "host": "0.0.0.0",
                "port": "8000",
                "log_level": "info",
                "limit_concurrency": "500"
            }
        
        try:
            api_process = await asyncio.create_subprocess_exec(
                "python", "-m", "uvicorn", "api.main:app",
                "--host", api_config.get("host", "0.0.0.0"),
                "--port", api_config.get("port", "8000"),
                "--log-level", api_config.get("log_level", "info"),
                "--limit-concurrency", api_config.get("limit_concurrency", "500"),
            )
            
            logger.info(f"[STARTUP] API server started on {api_config.get('host')}:{api_config.get('port')}")
            return api_process
            
        except Exception as e:
            logger.error(f"[STARTUP] Failed to start API server: {e}")
            raise
    
    async def run_main_loop(self):
        """
        Main event loop - just waits for background tasks.
        The actual scheduling is handled by the dispatcher.
        """
        logger.info("[STARTUP] Entering main event loop")
        
        try:
            # Wait for all background tasks
            await asyncio.gather(*self.background_tasks)
        except KeyboardInterrupt:
            logger.info("[STARTUP] Keyboard interrupt received")
        except Exception as e:
            logger.error(f"[STARTUP] Error in main loop: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown of all components."""
        logger.info("[STARTUP] Beginning shutdown sequence")
        
        # Stop the dispatcher
        await self.dispatcher.stop()
        
        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        logger.info("[STARTUP] Shutdown completed")
    
    def force_exit(self, api_process=None):
        """Emergency exit (maintains compatibility with legacy startup)."""
        logger.info("[STARTUP] Force exit requested")
        
        try:
            if api_process:
                api_process.kill()
        except Exception as e:
            logger.error(f"[STARTUP] Failed to kill API process: {e}")
        
        # Cancel all background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
        
        import os
        os._exit(1)
    
    async def get_system_status(self) -> Dict:
        """Get current system status."""
        dispatcher_status = await self.dispatcher.get_status()
        
        return {
            "startup_completed": len(self.background_tasks) > 0,
            "background_tasks": len(self.background_tasks),
            "dispatcher": dispatcher_status,
            "timestamp": datetime.now().isoformat()
        }