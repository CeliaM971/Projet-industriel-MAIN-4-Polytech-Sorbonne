from sqlmodel import SQLModel, Field

class TypannotCharacterBase(SQLModel):
    hex_code: str = Field(index=True, unique=True)  # ex: "E000"
    decimal_code: int = Field(unique=True)  # ex: 57347
    name: str                                         # ex: "Sélection droite"

class TypannotCharacter(TypannotCharacterBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

class TypannotCharacterPublic(TypannotCharacterBase):
    id: int

