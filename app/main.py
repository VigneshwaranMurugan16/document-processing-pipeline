from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.db.database import Base, engine


app = FastAPI(
    title="Document Processing Pipeline",
    version="0.1.0",
)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.include_router(health_router, prefix="/api/v1")

