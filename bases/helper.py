class BaseHelper:
    def __init__(
            self,
            id: str = None, # internal id (system + admin dash only)
            name: str = None, # readable name
            description: str = None, # readable description
            params: dict = None, # parameters for the helper
            internal: bool = False, # use if this is system level and NOT user-facing
            admin_only: bool = False, # only admins can **run** this helper
            require_admin_activation: bool = False, # this helper can only be activated by an admin. This does not mean that only admins can run it.
            boot_run: bool = False, # run at startup
            priority: int = 5, # priority for scheduling, from 1 (highest) to 5 (lowest)
            timeout: int = 100, # the maxium time in seconds this helper can run before being considered expired
            # Backward compatibility parameter
            run_at_start: bool = None, # legacy parameter for backward compatibility
        ):
        self.id = id
        self.name = name
        self.description = description
        self.params = params
        self.internal = internal
        self.admin_only = admin_only
        self.require_admin_activation = require_admin_activation
        
        # Handle backward compatibility
        if run_at_start is not None:
            self.boot_start = run_at_start
        else:
            self.boot_start = boot_run
            
        self.priority = priority
        self.timeout = timeout

    def run(self):
        raise NotImplementedError("Each helper must implement the 'run' method.")
    
    def schedule(self):
        """Legacy schedule method for backward compatibility."""
        pass  # Default implementation does nothing
    
    def get_schedule_config(self):
        """
        Return the schedule configuration for the new execution queue system.
        
        This method should be overridden by helpers to define their scheduling.
        
        Returns:
            dict: Schedule configuration with the following structure:
                {
                    "type": "daily" | "interval" | "cron",
                    "time": "HH:MM:SS" (for daily),
                    "interval_minutes": int (for interval),
                    "cron": "* * * * *" (for cron),
                    "priority": int (1-5, default 3),
                    "expiry": int (seconds after execution_time, default 300),
                    "enabled": bool (default True)
                }
        """
        # Default: use helper's priority and timeout
        return {
            "type": "interval",
            "interval_minutes": 60,  # Default 1 hour
            "priority": self.priority,
            "expiry": self.timeout,
            "enabled": True
        }
