from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=256)


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    is_system: bool

    model_config = {"from_attributes": True}


class RoleWithPermissions(RoleResponse):
    permissions: list[str] = []


class PermissionResponse(BaseModel):
    id: str
    code: str
    description: str

    model_config = {"from_attributes": True}


class AssignPermissions(BaseModel):
    permissions: list[str]


class AssignRole(BaseModel):
    role_id: str
