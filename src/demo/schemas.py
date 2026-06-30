from pydantic import BaseModel, Field


class ArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(default="")


class ArticleResponse(BaseModel):
    id: str
    title: str
    content: str
    author_id: str

    model_config = {"from_attributes": True}
