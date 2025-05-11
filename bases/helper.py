class BaseHelper:
    def __init__(self, run_at_start=False):
        self.run_at_start = run_at_start

    def run(self):
        raise NotImplementedError("Each helper must implement the 'run' method.")

    def schedule(self):
        raise NotImplementedError("Each helper must implement the 'schedule' method.")