"""
API v1 Main Router
"""
from fastapi import APIRouter
from app.api.v1.endpoints import health, chat, chat_streaming, conversations, voice

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

# Include streaming chat endpoint
apiRouter.include_router(
    chat_streaming.router,
    prefix="/chat",
    tags=["Chat Streaming"]
)

# Include conversations endpoints
apiRouter.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"]
)

# Include voice endpoints
apiRouter.include_router(
    voice.router,
    prefix="/voice",
    tags=["Voice"]
)
