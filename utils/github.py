import subprocess
import os

class GitHub:
    def get_latest_commit(args=None, **kwargs) -> str:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=os.getcwd()).decode('ascii').strip()