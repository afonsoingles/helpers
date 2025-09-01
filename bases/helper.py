class BaseHelper:
    def __init__(
            self,
            id: str = None, # internal id (system + admin dash only)
            name: str = None, # readable name
            description: str = None, # readable description
            user: dict = {}, # user running the helper
            params: dict = {}, # parameters for the helper
            internal: bool = False, # use if this is system level and NOT user-facing
            admin_only: bool = False, # only admins can **run** this helper
            require_admin_activation: bool = False, # this helper can only be activated by an admin. This does not mean that only admins can run it.
            boot_run: bool = False, # run at startup
            priority: int = 5, # priority for scheduling, from 5 (highest) to 1 (lowest)
            timeout: int = 100, # the maxium time in seconds this helper can run before being considered expired
            allow_execution_time_config: bool = True, # can the user configure the execution time of this helper
            disabled: bool = False, # disable the helper entirely
            schedule: list = [] # helper running schedule (only required if allow_execution_time_config is False)
        ):
        self.id = id
        self.name = name
        self.description = description
        self.user = user
        self.params = params
        self.internal = internal
        self.admin_only = admin_only
        self.require_admin_activation = require_admin_activation
        self.boot_run = boot_run
        self.priority = priority
        self.timeout = timeout
        self.allow_execution_time_config = allow_execution_time_config
        self.disabled = disabled
        self.schedule = schedule


    async def run(self):
        raise NotImplementedError("Each helper must implement the 'run' method.")