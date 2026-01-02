"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.v1 import router as v1_router
from app.config import get_settings
from app.core.exceptions import AIGatewayException
from app.database import init_db

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting AI Gateway...")
    
    # Initialize database tables
    await init_db()
    logger.info("Database initialized")
    
    # Create initial admin user if needed
    await create_initial_admin()
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Gateway...")


async def create_initial_admin():
    """Create initial admin user if not exists."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User
    from app.core.security import get_password_hash
    
    async with AsyncSessionLocal() as db:
        # Check if any user exists
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            return
        
        # Create admin user
        admin = User(
            email=settings.admin_email,
            username="admin",
            password_hash=get_password_hash(settings.admin_password),
            is_active=True,
            is_superuser=True,
            auth_provider="local",
        )
        db.add(admin)
        await db.commit()
        logger.info(f"Created initial admin user: {settings.admin_email}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI Gateway - LLM Proxy and Management Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(AIGatewayException)
async def ai_gateway_exception_handler(request: Request, exc: AIGatewayException):
    """Handle custom AI Gateway exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "An unexpected error occurred",
                "type": "internal_error",
            }
        },
    )


# Include routers
app.include_router(v1_router)  # OpenAI-compatible API
app.include_router(admin_router)  # Admin API


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs" if settings.debug else None,
    }
