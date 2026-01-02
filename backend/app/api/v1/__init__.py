"""OpenAI-compatible v1 API package."""
from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.embeddings import router as embeddings_router
from app.api.v1.models import router as models_router

router = APIRouter(prefix="/v1")
router.include_router(chat_router)
router.include_router(embeddings_router)
router.include_router(models_router)
