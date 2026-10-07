import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI

from src.api import events, health, sync
from src.clients.events_provider import EventsProviderClient
from src.config import settings
from src.db.session import session_factory
from src.services.sync import SyncRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = EventsProviderClient(
        settings.events_provider_url, settings.events_provider_api_key
    )
    app.state.events_provider = client
    app.state.sync_runner = SyncRunner(session_factory, client)
    worker = asyncio.create_task(app.state.sync_runner.run_forever())
    yield
    worker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker
    await client.close()


app = FastAPI(title="Events Aggregator", lifespan=lifespan)
app.include_router(health.router)
app.include_router(sync.router)
app.include_router(events.router)
