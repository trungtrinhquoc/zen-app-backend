"""
API v1 Main Router
"""
from fastapi import APIRouter

apiRouter = APIRouter()

# Health check for v1
@apiRouter.get("/health")
async def v1Health():
    return {"version": "1.0.0", "status": "ok"}