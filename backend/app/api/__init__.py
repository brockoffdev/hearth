from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .events import router as events_router
from .family import router as family_router
from .google import router as google_router
from .health import router as health_router
from .setup import router as setup_router
from .uploads import router as uploads_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(google_router, prefix="/google", tags=["google"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(setup_router, prefix="/setup", tags=["setup"])
router.include_router(uploads_router, prefix="/uploads", tags=["uploads"])
router.include_router(events_router, prefix="/events", tags=["events"])
router.include_router(family_router, prefix="/family", tags=["family"])
