from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import logging
from utils.github import GitHub
import api.errors.exceptions as exceptions
from main import logger
from api.errors.handlers import create_exception_handler
import api.routers.notifications
import api.routers.accounts


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, title="Helpers API", version="1.0.0")

# Routers
app.include_router(api.routers.notifications.router, tags=["Notifications"])
app.include_router(api.routers.accounts.router, tags=["Accounts"])


# Bcrypt - Ignore __about__ warning
logging.getLogger('passlib').setLevel(logging.ERROR)

# libs
github = GitHub()

@app.exception_handler(500)
async def internalServerError(request, exc):
    logger.error("[API] Internal Server Error", exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal Server Error", "type": "unknown"},
    )

@app.exception_handler(405)
async def methodNotAllowed(request, exc: Exception):
    return JSONResponse(
        status_code=405,
        content={"success": False, "message": "Method Not Allowed", "type": "method_not_allowed"},
    )

@app.exception_handler(404)
async def notFound(request, exc):
    return JSONResponse(
        status_code=404,
        content={"success": False, "message": "Not Found", "type": "not_found"},
    )

exceptionHandlers = {
    exceptions.GlobalApiError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "InternalServerError"),
    exceptions.BadRequest: (status.HTTP_400_BAD_REQUEST, "BadRequest"),
    exceptions.NotFound: (status.HTTP_404_NOT_FOUND, "NotFound"),
    exceptions.Unauthorized: (status.HTTP_401_UNAUTHORIZED, "Unauthorized"),
    exceptions.MethodNotAllowed: (status.HTTP_405_METHOD_NOT_ALLOWED, "MethodNotAllowed"),
    exceptions.Forbidden: (status.HTTP_403_FORBIDDEN, "Forbidden"),

}

for exc_class, (status_code, message) in exceptionHandlers.items():
    app.add_exception_handler(
        exc_class_or_status_code=exc_class,
        handler=create_exception_handler(status_code, message),
    )


@app.get("/")
async def root():
    return {"message": "hello world :)"}

@app.get("/health")
async def health():
    
    return {"success": True, "message": "OK", "commit": github.get_latest_commit()}

@app.get("/debug")
async def debug():
    return 1/0