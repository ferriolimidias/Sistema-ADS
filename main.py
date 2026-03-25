from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.auth import router as auth_router
from api.routes.campaign_builder import router as campaign_builder_router
from api.routes.dashboard import client_router as client_dashboard_router
from api.routes.dashboard import router as dashboard_router
from api.routes.media import router as media_router
from api.routes.platform_sync import router as platform_sync_router
from api.routes.public import router as public_router
from api.routes.webhooks import router as webhooks_router
from engines.utils.security import hash_password
from models.database import Base, SessionLocal, engine
from models import schema  # noqa: F401
from models.schema import Usuario, UsuarioRole

load_dotenv()


def seed_superadmin_if_needed():
    admin_email = os.getenv("SUPERADMIN_EMAIL", "ferriolimidias@gmail.com").strip().lower()
    admin_password = os.getenv("SUPERADMIN_PASSWORD", "").strip()
    if not admin_email or not admin_password:
        return

    db = SessionLocal()
    try:
        if db.query(Usuario).count() > 0:
            return

        admin_user = Usuario(
            email=admin_email,
            password_hash=hash_password(admin_password),
            role=UsuarioRole.ADMIN,
            needs_password_change=False,
            cliente_id=None,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_superadmin_if_needed()
    yield


app = FastAPI(title="Ferrioli Tráfego Core API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campaign_builder_router)
app.include_router(auth_router)
app.include_router(dashboard_router, tags=["Dashboard"])
app.include_router(client_dashboard_router, tags=["Client Dashboard"])
app.include_router(media_router)
app.include_router(public_router)
app.include_router(platform_sync_router, prefix="/api/sync")
app.include_router(webhooks_router, prefix="/webhook")
app.mount("/lp", StaticFiles(directory="public/lps"), name="landing_pages")
app.mount("/public", StaticFiles(directory="public"), name="public_assets")


@app.get("/health")
def health_check():
    return {"status": "online", "system": "Ferrioli Core API"}
