
from sqlmodel import Field, SQLModel

class Groupe(SQLModel, table=True):
    id : int | None = Field(default= None, primary_key=True)
    name : str

"""
class Video(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True)
    title: str
    path: str
    group_id : int | None = Field(default=None, foreign_key="groupe.id")

"""
