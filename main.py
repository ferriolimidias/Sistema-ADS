from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.campaign_builder import router as campaign_builder_router
from api.routes.platform_sync import router as platform_sync_router
from api.routes.webhooks import router as webhooks_router
from models.database import Base, engine
from models import schema  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Ferrioli Tráfego Core API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/lp", StaticFiles(directory="public/lps"), name="landing_pages")

app.include_router(campaign_builder_router)
app.include_router(platform_sync_router, prefix="/api/sync")
app.include_router(webhooks_router, prefix="/webhook")


@app.get("/health")
def health_check():
    return {"status": "online", "system": "Ferrioli Core API"}
