import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    postgres_user = os.getenv("POSTGRES_USER", "postgres").strip()
    postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres").strip()
    postgres_db = os.getenv("POSTGRES_DB", "ferrioli_traffic").strip()
    postgres_host = os.getenv("POSTGRES_HOST", "localhost").strip()
    postgres_port = os.getenv("POSTGRES_PORT", "5432").strip()
    DATABASE_URL = (
        f"postgresql+psycopg2://{postgres_user}:{postgres_password}"
        f"@{postgres_host}:{postgres_port}/{postgres_db}"
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
