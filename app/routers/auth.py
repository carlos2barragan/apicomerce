"""Autenticación: registro, login (JWT) y datos del usuario actual."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.common import ErrorResponse
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un usuario",
    description=(
        "Crea una cuenta nueva. El **email debe ser único** y la contraseña "
        "se guarda **hasheada con bcrypt** (nunca en texto plano)."
    ),
    responses={400: {"model": ErrorResponse, "description": "El email ya está registrado"}},
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="El email ya está registrado"
        ) from exc
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión (obtener token JWT)",
    description=(
        "Se envía como `application/x-www-form-urlencoded` con los campos "
        "`username` (= tu email) y `password`. Devuelve un **token Bearer** que "
        "debes enviar en el header `Authorization: Bearer <token>` en las rutas "
        "protegidas."
    ),
    responses={401: {"model": ErrorResponse, "description": "Credenciales incorrectas"}},
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    # OAuth2PasswordRequestForm entrega el email en el campo "username".
    user = db.scalar(select(User).where(User.email == form_data.username))
    if (
        not user
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    return Token(access_token=create_access_token(subject=str(user.id)))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Usuario autenticado actual",
    description="Devuelve los datos del usuario dueño del token enviado.",
    responses={401: {"model": ErrorResponse, "description": "Token ausente o inválido"}},
)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
