from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.base.auth.deps import get_current_user
from src.base.auth.models import User
from src.base.tenant.deps import get_current_tenant
from src.db.session import get_db
from src.demo.schemas import ArticleCreate, ArticleResponse
from src.demo.service import create_article, list_articles, get_article
from src.rbac.deps import require_permission

router = APIRouter(tags=["demo"])


@router.post("/articles", status_code=201, response_model=ArticleResponse)
async def create(
    data: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("article:create")),
):
    """创建文章 — 自动绑定当前用户为作者，租户隔离"""
    return await create_article(db, data, user.id, tenant_id)


@router.get("/articles", response_model=list[ArticleResponse])
async def list_all(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("article:read")),
):
    """文章列表 — 自动过滤当前租户"""
    return await list_articles(db, tenant_id)


@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_one(
    article_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    _: None = Depends(require_permission("article:read")),
):
    """文章详情 — 自动校验租户所有权"""
    return await get_article(db, article_id, tenant_id)
