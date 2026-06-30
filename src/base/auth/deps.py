from redis.asyncio import Redis
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.models import User
from src.db.session import get_db
from src.system.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_redis(request: Request) -> Redis:
    """Reuse the app-level Redis connection pool from lifespan."""
    return request.app.state.redis


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    if await redis.exists(f"blacklist:{token}"):
        raise HTTPException(401, "Token已失效")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "无效的 token 类型")
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Token 无效")
    except JWTError:
        raise HTTPException(401, "Token 无效")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")
    return user
