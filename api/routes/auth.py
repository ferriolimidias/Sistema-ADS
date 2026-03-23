from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.utils.audit import registrar_log_safe
from engines.utils.security import create_access_token, get_current_user, hash_password, verify_password
from models.database import get_db
from models.schema import Usuario

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdatePasswordRequest(BaseModel):
    new_password: str
    confirm_password: str
    current_password: str | None = None


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        try:
            registrar_log_safe(
                db=db,
                user_id=(user.id if user else None),
                acao="LOGIN_FALHA",
                recurso=f"Auth Login: {payload.email.strip().lower()}",
                detalhes={"motivo": "Credenciais invalidas"},
                request=request,
            )
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Email ou senha invalidos.")

    token = create_access_token(user)
    try:
        registrar_log_safe(
            db=db,
            user_id=user.id,
            acao="LOGIN",
            recurso=f"Auth Login: {user.email}",
            detalhes={"resultado": "sucesso"},
            request=request,
        )
    except Exception:
        pass
    return {
        "status": "sucesso",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "needs_password_change": bool(user.needs_password_change),
            "cliente_id": user.cliente_id,
        },
    }


@router.get("/me")
def me(current_user: Usuario = Depends(get_current_user)):
    cliente = current_user.cliente
    return {
        "status": "sucesso",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            "needs_password_change": bool(current_user.needs_password_change),
            "cliente_id": current_user.cliente_id,
            "nome": (cliente.nome if cliente else "Super Admin"),
        },
    }


@router.put("/update-password")
def update_password(
    payload: UpdatePasswordRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Confirmacao de senha nao confere.")
    if len(payload.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 8 caracteres.")

    if not current_user.needs_password_change:
        if not payload.current_password:
            raise HTTPException(status_code=400, detail="Senha atual obrigatoria para alterar a senha.")
        if not verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Senha atual invalida.")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.needs_password_change = False
    db.commit()
    db.refresh(current_user)

    token = create_access_token(current_user)
    return {
        "status": "sucesso",
        "mensagem": "Senha atualizada com sucesso.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            "needs_password_change": False,
            "cliente_id": current_user.cliente_id,
        },
    }
