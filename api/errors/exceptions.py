class GlobalApiError(Exception):
    """API Error"""

    def __init__(self, message: str = "", type: str = ""):
        self.message = message
        self.type = type
        super().__init__(self.message, self.type)


class BadRequest(GlobalApiError):
    """Bad Request"""

    def __init__(self, message: str = "", type: str = ""):
        super().__init__(message, type)

class NotFound(GlobalApiError):
    """Not Found"""

    def __init__(self, message: str = "", type: str = ""):
        super().__init__(message, type)

class Unauthorized(GlobalApiError):
    """Unauthorized"""

    def __init__(self, message: str = "", type: str = ""):
        super().__init__(message, type)

class MethodNotAllowed(GlobalApiError):
    """Method Not Allowed"""

    def __init__(self, message: str = "", type: str = ""):
        super().__init__(message, type)

class Forbidden(GlobalApiError):
    """Forbidden"""

    def __init__(self, message: str = "", type: str = ""):
        super().__init__(message, type)

class Conflict(GlobalApiError):
    """Conflict"""

    def __init__(self, message: str = "", type: str = ""):
        super().__init__(message, type)