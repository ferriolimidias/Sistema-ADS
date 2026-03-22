import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise ValueError("REDIS_URL nao configurada no ambiente.")

celery_app = Celery(
    "ferrioli_geco",
    broker=REDIS_URL,
    include=["workers.geco_tasks"],
)

celery_app.conf.timezone = "America/Sao_Paulo"
celery_app.conf.beat_schedule = {
    "otimizador-geco-cortar-sangria-a-cada-2-horas": {
        "task": "workers.geco_tasks.otimizador_geco_cortar_sangria",
        "schedule": crontab(minute=0, hour="*/2"),
    }
}
