"""
API v1 router - combines all endpoint routers.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import auth

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(matters.router, prefix="/matters", tags=["matters"])
# api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# api_router.include_router(entities.router, prefix="/entities", tags=["entities"])
# api_router.include_router(events.router, prefix="/events", tags=["events"])
# api_router.include_router(checks.router, prefix="/checks", tags=["checks"])
