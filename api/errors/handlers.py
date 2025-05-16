from fastapi.responses import JSONResponse
from fastapi import Request
from typing import Callable
from api.errors.exceptions import GlobalApiError



def create_exception_handler(status_code: int, initial_detail: str) -> Callable[[Request, GlobalApiError], JSONResponse]:
    detail = {"message": initial_detail}

    async def exception_handler(_: Request, exc: GlobalApiError) -> JSONResponse:
        if exc.message:
            detail["message"] = exc.message

        if exc.type:
            detail["type"] = exc.type

        return JSONResponse(
            status_code=status_code, content={"success": False, "message": detail["message"], "type": detail["type"]}
        )

    return exception_handler