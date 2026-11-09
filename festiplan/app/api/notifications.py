from fastapi import APIRouter, Depends
from app.application.notifications import RetryPendingNotifications
from app.infrastructure.wiring import get_pending_store, get_retry_notifications
from app.schemas import PendingNotificationRead, RetryReportRead

router=APIRouter(prefix="/notifications",tags=["notifications"])

@router.get("/pending",response_model=list[PendingNotificationRead])
def list_pending(store=Depends(get_pending_store)):
    return store.list()

@router.post("/retry",response_model=RetryReportRead)
def retry_pending(use_case:RetryPendingNotifications=Depends(get_retry_notifications)):
    return use_case.execute()
