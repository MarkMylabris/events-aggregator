from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.domain.entities import SyncStatus
from src.services.sync import SyncRunner

router = APIRouter()


@router.post("/api/sync/trigger")
async def trigger_sync(request: Request) -> JSONResponse:
    runner: SyncRunner = request.app.state.sync_runner
    result = await runner.run()
    return JSONResponse(
        status_code=200 if result.status == SyncStatus.SUCCESS else 502,
        content={
            "status": result.status,
            "synced_events": result.synced_events,
            "last_changed_at": (
                result.last_changed_at.isoformat() if result.last_changed_at else None
            ),
            "error": result.error,
        },
    )
