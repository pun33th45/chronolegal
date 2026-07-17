from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    search,
    cases,
    analytics,
    admin,
    ner,
    timeline,
    summary,
    feedback,
    documents,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat & QA"])
api_router.include_router(search.router, prefix="/search", tags=["Legal Search"])
api_router.include_router(cases.router, prefix="/cases", tags=["Legal Cases"])
api_router.include_router(summary.router, prefix="/summary", tags=["Case Summary"])
api_router.include_router(ner.router, prefix="/ner", tags=["Named Entity Recognition"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["Timeline"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
