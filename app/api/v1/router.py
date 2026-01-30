"""
API v1 Main Router
"""
from fastapi import APIRouter
from app.api.v1.endpoints import health, chat

apiRouter = APIRouter()

apiRouter.include_router(
    health.router,
    tags=["Health"]
)

# Include chat endpoints
apiRouter.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"]
)