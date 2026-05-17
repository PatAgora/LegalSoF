"""
API v1 router - combines all endpoint routers.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, transactions, sof_assessment, matters,
    statement_validation, mfa, audit, notifications,
    document_verification, analytics,
)

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(mfa.router, prefix="/auth/mfa", tags=["mfa"])
api_router.include_router(transactions.router, tags=["transactions"])
api_router.include_router(sof_assessment.router, tags=["sof-assessment"])
api_router.include_router(matters.router, tags=["matters"])
api_router.include_router(statement_validation.router, tags=["statement-validation"])
api_router.include_router(audit.router, tags=["audit"])
api_router.include_router(notifications.router, tags=["notifications"])
api_router.include_router(document_verification.router, tags=["document-verification"])
api_router.include_router(analytics.router, tags=["analytics"])
