"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import apiRouter
from app.utils.logger import logger
from app.database import verifyDatabaseConnections, closeConnections


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    
    Chạy khi app START và SHUTDOWN
    """
    # ========== STARTUP ==========
    logger.info("=" * 70)
    logger.info(f"🚀 {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"📍 Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 70)
    
    # Test database connections
    #logger.info("🔌 Testing database connections...")
    try:
        connections = await verifyDatabaseConnections()
        
        # Log Supabase status
        supabase = connections["supabase"]
        # if supabase["status"] == "connected":
        #     logger.info(f"✅ Supabase: {supabase['message']}")
        # else:
        #     logger.error(f"❌ Supabase: {supabase['message']}")
        
        # Log SQLAlchemy status
        sqlalchemy = connections["sqlalchemy"]
        # if sqlalchemy["status"] == "connected":
        #     logger.info(f"✅ SQLAlchemy: {sqlalchemy['message']}")
        # else:
        #     logger.error(f"❌ SQLAlchemy: {sqlalchemy['message']}")
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
    
    # logger.info("=" * 70)
    # logger.info("✅ Application startup complete")
    # logger.info(f"📚 Docs: http://localhost:8000/docs")
    # logger.info("=" * 70)
    
    yield  # Application is running
    
    # ========== SHUTDOWN ==========
    logger.info("=" * 70)
    logger.info(f"🛑 {settings.PROJECT_NAME} shutting down...")
    logger.info("=" * 70)
    
    # Close database connections
    await closeConnections()
    
    logger.info("✅ Shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI Backend for Zen APP - Emotional Support Companion",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "disabled in production",
        "health": "/api/v1/health"
    }


# Include API v1 router
app.include_router(apiRouter, prefix="/api/v1")


# Global exception handler
@app.exception_handler(Exception)
async def globalExceptionHandler(request, exc):
    """Bắt tất cả exceptions chưa được handle"""
    logger.error(f"❌ Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__ if settings.DEBUG else None
        }
    )