from fastapi import FastAPI
import api.routers.notifications
import api.routers.webhooks

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, title="Helpers API", version="1.0.0")

app.include_router(api.routers.notifications.router, prefix="/v1/notifications", tags=["Notifications"])
app.include_router(api.routers.webhooks.router, prefix="/v1/webhooks", tags=["Webhooks"])