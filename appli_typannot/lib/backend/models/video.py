from datetime import datetime
from sqlmodel import SQLModel, Field


class VideoBase(SQLModel):
    title: str = Field(index=True)
    description: str | None = None
    file_path: str


class Video(VideoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VideoPublic(VideoBase):
    id: int
    group_id: int
    created_at: datetime


class VideoCreate(SQLModel):
    title: str
    description: str | None = None
    group_id: int


class VideoRename(SQLModel):
    title: str
