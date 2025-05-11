class Monitor:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def run(self):
        raise NotImplementedError("Each monitor must implement the 'run' method.")
    
    def stop(self):
        raise NotImplementedError("Each monitor must implement the 'stop' method.")