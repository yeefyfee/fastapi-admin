from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from jose import jwt, JWTError
from src.base.auth.schemas import UserRegister, UserResponse, TokenResponse, RefreshRequest
from src.base.auth.service import (
    register_user, authenticate_user, create_access_token, create_refresh_token,
)
from src.base.auth.deps import get_current_user, get_redis, oauth2_scheme
from src.base.auth.models import User
from src.db.session import get_db
from src.system.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user = await authenticate_user(db, form.username, form.password)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    await redis.setex(f"refresh:{user.id}", 60 * 60 * 24 * 7, refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    try:
        payload = jwt.decode(body.refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "无效的 refresh token")
        user_id = payload["sub"]
    except JWTError:
        raise HTTPException(401, "Refresh token 无效")
    stored = await redis.get(f"refresh:{user_id}")
    if stored != body.refresh_token:
        raise HTTPException(401, "Refresh token 不匹配")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    await redis.setex(f"refresh:{user_id}", 60 * 60 * 24 * 7, new_refresh)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    redis: Redis = Depends(get_redis),
):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Token 无效")
    exp = payload.get("exp", 0)
    import time
    ttl = max(int(exp - time.time()), 1)
    await redis.setex(f"blacklist:{token}", ttl, "1")
    return {"message": "已登出"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
