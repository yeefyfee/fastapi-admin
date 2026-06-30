from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from src.demo.models import Article
from src.demo.schemas import ArticleCreate


async def create_article(db: AsyncSession, data: ArticleCreate, author_id: str, tenant_id: str) -> Article:
    article = Article(
        title=data.title,
        content=data.content,
        author_id=author_id,
        tenant_id=tenant_id,
    )
    db.add(article)
    await db.flush()
    await db.refresh(article)
    return article


async def list_articles(db: AsyncSession, tenant_id: str) -> list[Article]:
    result = await db.scalars(
        select(Article)
        .where(Article.tenant_id == tenant_id)
        .order_by(Article.created_at.desc())
    )
    return list(result.all())


async def get_article(db: AsyncSession, article_id: str, tenant_id: str) -> Article:
    article = await db.get(Article, article_id)
    if not article or article.tenant_id != tenant_id:
        raise HTTPException(404, "文章不存在")
    return article
