
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base
from supabase import create_client, Client
from typing import AsyncGenerator, Optional
from sqlalchemy import text

from app.core.config import settings
from app.utils.logger import logger


# ============================================
# BASE CLASS CHO MODELS
# ============================================
Base = declarative_base()


# ============================================
# SUPABASE CLIENT (Singleton)
# ============================================
_supabaseClient: Optional[Client] = None


def getSupabase() -> Client:
    """
    Lấy Supabase client (singleton pattern)
    
    Giải thích:
    - Chỉ tạo 1 instance duy nhất cho toàn bộ app
    - Dùng cho Auth, Storage, RLS queries
    
    Usage:
        from app.database import getSupabase
        
        supabase = getSupabase()
        result = supabase.table("users").select("*").execute()
    """
    global _supabaseClient
    
    if _supabaseClient is None:
        try:
            _supabaseClient = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_KEY
            )
            #logger.info("✅ Supabase client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase: {e}")
            raise
    
    return _supabaseClient


# ============================================
# SQLALCHEMY ASYNC ENGINE
# ============================================

# Chuyển đổi connection string
# postgresql:// -> postgresql+asyncpg:// (async driver)
# Loại bỏ các query parameters không được hỗ trợ bởi asyncpg
DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql://", 
    "postgresql+asyncpg://"
).split("?")[0]  # Loại bỏ ?pgbouncer=true và các params khác

# Tạo async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Log SQL queries khi DEBUG=True
    future=True,  # SQLAlchemy 2.0 style
    pool_pre_ping=True,  # Test connection trước khi dùng
    pool_size=10,  # Số connections trong pool
    max_overflow=20,  # Max connections khi pool đầy
    pool_recycle=3600,  # Recycle connection sau 1 giờ
    connect_args={
        "statement_cache_size": 0,  # Tắt prepared statements cho pgbouncer
        "server_settings": {
            "application_name": "zen-app-backend"
        }
    }
)

#logger.info("✅ SQLAlchemy async engine created")


# Tạo session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  
    autocommit=False,  
    autoflush=False,  
)


def getEngine() -> AsyncEngine:
    """
    Lấy SQLAlchemy engine
    
    Usage:
        from app.database import getEngine
        
        engine = getEngine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
    """
    return engine


async def getDbSession() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function để inject DB session vào FastAPI endpoints
    
    Giải thích:
    - Tạo session mới cho mỗi request
    - Tự động commit nếu không có exception
    - Tự động rollback nếu có exception
    - Tự động close session sau khi request xong
    
    Usage trong FastAPI:
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.database import getDbSession
        
        @router.get("/users")
        async def getUsers(db: AsyncSession = Depends(getDbSession)):
            result = await db.execute(select(User))
            users = result.scalars().all()
            return users
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Auto commit nếu không có exception
        except Exception:
            await session.rollback()  # Rollback nếu có lỗi
            raise
        finally:
            await session.close()


# ============================================
# TEST CONNECTIONS
# ============================================

async def verifySupabaseConnection() -> dict:
    """
    Test Supabase client connection
    
    Giải thích:
    - Thử query bảng users để verify connection
    - Không cần dữ liệu, chỉ cần không lỗi
    """
    try:
        supabase = getSupabase()
        # Query đơn giản để test
        supabase.table("users").select("id").limit(1).execute()
        
        logger.info("✅ Supabase connection successful")
        return {
            "status": "connected",
            "message": "Supabase connection successful",
            "type": "Supabase Client"
        }
    except Exception as e:
        logger.error(f"❌ Supabase connection test failed: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "type": "Supabase Client"
        }


async def verifySQLAlchemyConnection() -> dict:
    """
    Test SQLAlchemy engine connection
    
    Giải thích:
    - Chạy query "SELECT 1" để verify connection
    - Test connection pool có hoạt động không
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        
        #logger.info("✅ SQLAlchemy connection test successful")
        return {
            "status": "connected",
            "message": "SQLAlchemy connection successful",
            "type": "SQLAlchemy Async Engine"
        }
    except Exception as e:
        logger.error(f"❌ SQLAlchemy connection test failed: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "type": "SQLAlchemy Async Engine"
        }


async def verifyDatabaseConnections() -> dict:
    """
    Test tất cả database connections
    
    Giải thích:
    - Chạy cả 2 tests song song (parallel) để nhanh hơn
    - asyncio.gather chạy nhiều async functions đồng thời
    
    Returns:
        dict: Status của Supabase và SQLAlchemy
    
    Usage:
        from app.database import testConnections
        
        status = await testConnections()
        print(status)
    """
    import asyncio
    
    # Chạy 2 tests song song
    supabaseResult, sqlalchemyResult = await asyncio.gather(
        verifySupabaseConnection(),
        verifySQLAlchemyConnection(),
        return_exceptions=True 
    )
    
    # Format results
    return {
        "supabase": supabaseResult if isinstance(supabaseResult, dict) else {
            "status": "error",
            "message": str(supabaseResult),
            "type": "Supabase Client"
        },
        "sqlalchemy": sqlalchemyResult if isinstance(sqlalchemyResult, dict) else {
            "status": "error",
            "message": str(sqlalchemyResult),
            "type": "SQLAlchemy Async Engine"
        }
    }


async def closeConnections():
    """
    Đóng tất cả database connections
    
    Giải thích:
    - Gọi khi app shutdown
    - Dispose engine sẽ đóng tất cả connections trong pool
    """
    await engine.dispose()
    logger.info("🔌 Database connections closed")