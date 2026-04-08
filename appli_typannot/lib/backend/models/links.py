from datetime import datetime
from sqlmodel import SQLModel, Field


class UserGroup(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id", primary_key=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class UserCurrentGroup(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserVideo(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    video_id: int = Field(foreign_key="video.id", primary_key=True)
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    is_owner: bool = Field(default=False)
