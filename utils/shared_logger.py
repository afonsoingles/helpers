"""
Shared logger instance to avoid circular imports.
This module provides a global logger that can be imported by helpers and other modules.
"""

import logging
import os
from datetime import datetime
from colorama import init, Fore, Style
import sentry_sdk

init(autoreset=True)

class SharedLogger:
    """Simplified logger that matches the existing Logger interface."""
    
    def __init__(self):
        # Create logs directory
        os.makedirs("data/logs", exist_ok=True)
        self.start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file_path = os.path.join("data", "logs", f"shared_{self.start_time}.log")
        
        try:
            self.log_file = open(self.log_file_path, "a", encoding="utf-8")
        except Exception:
            self.log_file = None
    
    def _write_log(self, level: str, message: str, color: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        # Print to console
        try:
            print(color + formatted + Style.RESET_ALL)
        except Exception:
            print(formatted)
        
        # Write to file
        if self.log_file:
            try:
                self.log_file.write(formatted + "\n")
                self.log_file.flush()
            except Exception:
                pass
        
        # Send to Sentry if configured
        try:
            if level == "ERROR":
                sentry_sdk.capture_message(message, level="error")
            elif level == "WARN":
                sentry_sdk.capture_message(message, level="warning")
        except Exception:
            pass
    
    def debug(self, message: str):
        self._write_log("DEBUG", message, Fore.LIGHTBLACK_EX)
    
    def info(self, message: str):
        self._write_log("INFO", message, Fore.GREEN)
    
    def warn(self, message: str):
        self._write_log("WARN", message, Fore.YELLOW)
    
    def error(self, message, exception: Exception = None):
        if exception:
            try:
                sentry_sdk.capture_exception(exception)
                self._write_log("ERROR", f"{message}: {exception}", Fore.RED)
            except Exception:
                self._write_log("ERROR", str(message), Fore.RED)
        else:
            self._write_log("ERROR", str(message), Fore.RED)
    
    def __del__(self):
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass

# Create shared logger instance
logger = SharedLogger()