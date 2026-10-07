import logging

from fastapi import FastAPI

from src.api import health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Events Aggregator")
app.include_router(health.router)
