import subprocess

class GitHub:
    def get_latest_commit(args=None, **kwargs) -> str:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()