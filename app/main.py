"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1.router import apiRouter
from app.utils.logger import logger


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def healthCheck():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


# Include API router
app.include_router(apiRouter, prefix="/api/v1")


# Global exception handler
@app.exception_handler(Exception)
async def globalExceptionHandler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Startup event
@app.on_event("startup")
async def startup():
    logger.info(f"{settings.PROJECT_NAME} v{settings.VERSION} starting...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown():
    logger.info(f"{settings.PROJECT_NAME} shutting down...")