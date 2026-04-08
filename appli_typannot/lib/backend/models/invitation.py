from datetime import datetime
from pydantic import EmailStr
from sqlmodel import SQLModel, Field


class GroupInvitation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    inviter_user_id: int = Field(foreign_key="user.id", index=True)
    invitee_email: EmailStr = Field(index=True)
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InviteRequest(SQLModel):
    email: EmailStr


class InvitationDecision(SQLModel):
    decision: str
