"""Admin API package."""
from fastapi import APIRouter

from app.api.admin.auth import router as auth_router
from app.api.admin.users import router as users_router
from app.api.admin.providers import router as providers_router
from app.api.admin.models import router as models_router
from app.api.admin.logs import router as logs_router
from app.api.admin.stats import router as stats_router
from app.api.admin.organizations import router as organizations_router
from app.api.admin.model_access import router as model_access_router
from app.api.admin.pii import router as pii_router
from app.api.admin.pii_models import router as pii_models_router
from app.api.admin.security_scan import router as security_scan_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(providers_router)
router.include_router(models_router)
router.include_router(logs_router)
router.include_router(stats_router)
router.include_router(organizations_router)
router.include_router(model_access_router)
router.include_router(pii_router)
router.include_router(pii_models_router)
router.include_router(security_scan_router)
