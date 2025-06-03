import os
import sentry_sdk
from datetime import datetime
from colorama import init, Fore, Style
import sentry_sdk.logger


init(autoreset=True)

class Logger:
    def __init__(self):
        
        os.makedirs("data/logs", exist_ok=True)
        self.start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file_path = os.path.join("data", "logs", f"{self.start_time}.log")

        self.log_file = open(self.log_file_path, "a", encoding="utf-8")

    def _write_log(self, level: str, message: str, color: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        print(color + formatted + Style.RESET_ALL)

        self.log_file.write(formatted + "\n")
        self.log_file.flush()
        match level:
            case "ERROR":
                sentry_sdk.logger.error(message)
            case "WARN":
                sentry_sdk.logger.warning(message)
            case "INFO":
                sentry_sdk.logger.info(message)
            case "DEBUG":
                sentry_sdk.logger.debug(message)
        

    def debug(self, message: str):
        self._write_log("DEBUG", message, Fore.LIGHTBLACK_EX)

    def info(self, message: str):
        self._write_log("INFO", message, Fore.GREEN)

    def warn(self, message: str):
        self._write_log("WARN", message, Fore.YELLOW)

    def error(self, message, exception: Exception = None):

        sentry_sdk.capture_exception(exception)
        self._write_log("ERROR", message=f"{message}: {exception}", color=Fore.RED)

    def __del__(self):
        try:
            self.log_file.close()
        except Exception:
            pass
