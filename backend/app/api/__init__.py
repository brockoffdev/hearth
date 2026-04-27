from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .google import router as google_router
from .health import router as health_router
from .setup import router as setup_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(google_router, prefix="/google", tags=["google"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(setup_router, prefix="/setup", tags=["setup"])
