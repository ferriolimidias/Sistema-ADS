import os

from sqlalchemy.orm import Session

from models.database import SessionLocal
from models.schema import ConsumoIA

MODEL_ANALYSIS = (os.getenv("MODEL_ANALYSIS") or "gpt-4o-mini").strip()
MODEL_STRATEGY = (os.getenv("MODEL_STRATEGY") or "gpt-4o").strip()

PRICE_PER_MILLION_INPUT = {
    "gpt-4o-mini": 0.15,
    "gpt-4o": 5.00,
}
PRICE_PER_MILLION_OUTPUT = {
    "gpt-4o-mini": 0.60,
    "gpt-4o": 15.00,
}


def calcular_custo_estimado(modelo: str, tokens_in: int, tokens_out: int) -> float:
    model_key = str(modelo or "").strip()
    in_price = float(PRICE_PER_MILLION_INPUT.get(model_key, 0.15))
    out_price = float(PRICE_PER_MILLION_OUTPUT.get(model_key, 0.60))
    custo = (float(tokens_in or 0) / 1_000_000.0) * in_price + (float(tokens_out or 0) / 1_000_000.0) * out_price
    return float(round(custo, 8))


def registrar_consumo_ia(
    db: Session | None,
    modelo: str,
    tokens_in: int,
    tokens_out: int,
    tarefa: str,
) -> None:
    custo_estimado = calcular_custo_estimado(modelo=modelo, tokens_in=tokens_in, tokens_out=tokens_out)
    created_session = False
    session = db
    if session is None:
        session = SessionLocal()
        created_session = True
    try:
        row = ConsumoIA(
            modelo=str(modelo or "").strip(),
            tarefa=str(tarefa or "").strip(),
            tokens_input=int(tokens_in or 0),
            tokens_output=int(tokens_out or 0),
            custo_estimado=float(custo_estimado),
        )
        session.add(row)
        session.commit()
    except Exception:
        if created_session:
            session.rollback()
    finally:
        if created_session:
            session.close()
