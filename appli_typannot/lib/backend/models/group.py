from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlmodel import SQLModel

class GroupBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = None


class Group(GroupBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_personal: bool = Field(default=False, index=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)


class GroupPublic(GroupBase):
    id: int
    created_at: datetime
    is_personal: bool
    owner_user_id: int | None


class GroupCreate(GroupBase):
    pass

class GroupUpdate(SQLModel):
    name: str | None = None
    description: str | None = None

class CurrentGroupUpdate(SQLModel):
    group_id: int


class LeaveGroupRequest(SQLModel):
    new_owner_user_id: int | None = None

