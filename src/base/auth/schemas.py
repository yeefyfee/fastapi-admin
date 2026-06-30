from pydantic import BaseModel, EmailStr, Field


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(default="", max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_super_admin: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
