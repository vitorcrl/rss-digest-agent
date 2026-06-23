from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.api.v1.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="RSS Digest Agent", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")
