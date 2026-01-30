"""
Health Check Endpoints
Kiểm tra trạng thái hệ thống
"""
from fastapi import APIRouter, status
from datetime import datetime

from app.core.config import settings
from app.database import verifyDatabaseConnections

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def healthCheck():
    """
    Basic health check
    
    Giải thích:
    - Endpoint đơn giản để check API có sống không
    - Không test database, chỉ return status
    - Dùng cho load balancer health check
    
    Response:
    {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "development",
        "timestamp": "2024-01-30T10:00:00.000000"
    }
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/database", status_code=status.HTTP_200_OK)
async def databaseHealthCheck():
    """
    Database health check
    
    Giải thích:
    - Test cả Supabase và SQLAlchemy connections
    - Chạy song song (parallel) để nhanh
    - Return detail status của từng connection
    
    Response:
    {
        "status": "healthy",
        "timestamp": "...",
        "connections": {
            "supabase": {"status": "connected", "message": "..."},
            "sqlalchemy": {"status": "connected", "message": "..."}
        }
    }
    """
    connections = await verifyDatabaseConnections()
    
    allConnected = (
        connections["supabase"]["status"] == "connected" and
        connections["sqlalchemy"]["status"] == "connected"
    )
    
    return {
        "status": "healthy" if allConnected else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "connections": connections
    }


@router.get("/health/full", status_code=status.HTTP_200_OK)
async def fullHealthCheck():
    """
    Full system health check
    
    Giải thích:
    - Check tất cả services: Database, OpenRouter
    - Dùng cho monitoring tools (Datadog, New Relic...)
    - Return comprehensive status
    
    Response:
    {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "development",
        "timestamp": "...",
        "services": {
            "database": {...},
            "openrouter": {"status": "configured", "model": "openai/gpt-4o-mini"}
        }
    }
    """
    dbHealth = await databaseHealthCheck()
    
    # Check OpenRouter config
    openrouterConfigured = bool(
        settings.OPENROUTER_API_KEY and
        settings.OPENROUTER_API_KEY.startswith("sk-or-")
    )
    
    openrouterStatus = {
        "status": "configured" if openrouterConfigured else "not_configured",
        "model": settings.OPENROUTER_MODEL
    }
    
    overallHealthy = (
        dbHealth["status"] == "healthy" and
        openrouterConfigured
    )
    
    return {
        "status": "healthy" if overallHealthy else "unhealthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": dbHealth,
            "openrouter": openrouterStatus
        }
    }


"""
Giải thích Health Checks:

1. WHY?
   - Verify hệ thống hoạt động
   - Load balancer cần biết server nào healthy
   - Monitoring tools track uptime
   
2. Levels:
   - /health: Basic (API alive?)
   - /health/database: Database connected?
   - /health/full: All services OK?
   
3. Usage:
   - Docker: HEALTHCHECK --interval=30s CMD curl /health
   - Kubernetes: livenessProbe.httpGet.path: /health
   - Monitoring: Poll /health/full every minute
"""