import subprocess

class GitHub:
    def get_latest_commit():
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()