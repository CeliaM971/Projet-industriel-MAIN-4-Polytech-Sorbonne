from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from db import SessionDep
from models.TypannotCharacter import TypannotCharacter, TypannotCharacterPublic, TypannotCharacterBase
from security import CurrentUser

router = APIRouter(prefix="/typannot", tags=["Typannot"])


# =====================================================
# LISTER TOUS LES CARACTÈRES
# =====================================================
@router.get(
    "/characters",
    response_model=list[TypannotCharacterPublic],
    summary="Récupérer tous les caractères Typannot"
)
def list_characters(session: SessionDep, current_user: CurrentUser):
    return session.exec(select(TypannotCharacter)).all()


# =====================================================
# LISTER PAR CATÉGORIE
# =====================================================
@router.get(
    "/characters/category/{category}",
    response_model=list[TypannotCharacterPublic],
    summary="Récupérer les caractères d'une catégorie"
)
def list_by_category(category: str, session: SessionDep, current_user: CurrentUser):
    return session.exec(
        select(TypannotCharacter).where(TypannotCharacter.category == category)
    ).all()


# =====================================================
# RÉCUPÉRER UN CARACTÈRE PAR SON CODE HEX
# =====================================================
@router.get(
    "/characters/{hex_code}",
    response_model=TypannotCharacterPublic,
    summary="Récupérer un caractère par son code hexadécimal"
)
def get_character(hex_code: str, session: SessionDep, current_user: CurrentUser):
    character = session.exec(
        select(TypannotCharacter).where(TypannotCharacter.hex_code == hex_code)
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Caractère {hex_code} introuvable")
    return character


# =====================================================
# CRÉER UN CARACTÈRE (admin)
# =====================================================
@router.post(
    "/characters",
    response_model=TypannotCharacterPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un caractère Typannot"
)
def create_character(data: TypannotCharacterBase, session: SessionDep, current_user: CurrentUser):
    existing = session.exec(
        select(TypannotCharacter).where(TypannotCharacter.hex_code == data.hex_code)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Le caractère {data.hex_code} existe déjà")

    character = TypannotCharacter(**data.model_dump())
    session.add(character)
    session.commit()
    session.refresh(character)
    return character


# =====================================================
# MODIFIER UN CARACTÈRE
# =====================================================
@router.patch(
    "/characters/{hex_code}",
    response_model=TypannotCharacterPublic,
    summary="Modifier un caractère Typannot"
)
def update_character(hex_code: str, data: TypannotCharacterBase, session: SessionDep, current_user: CurrentUser):
    character = session.exec(
        select(TypannotCharacter).where(TypannotCharacter.hex_code == hex_code)
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Caractère {hex_code} introuvable")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(character, key, value)

    session.add(character)
    session.commit()
    session.refresh(character)
    return character


# =====================================================
# SUPPRIMER UN CARACTÈRE
# =====================================================
@router.delete(
    "/characters/{hex_code}",
    status_code=status.HTTP_200_OK,
    summary="Supprimer un caractère Typannot"
)
def delete_character(hex_code: str, session: SessionDep, current_user: CurrentUser):
    character = session.exec(
        select(TypannotCharacter).where(TypannotCharacter.hex_code == hex_code)
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail=f"Caractère {hex_code} introuvable")

    session.delete(character)
    session.commit()
    return {"ok": True, "message": f"Caractère {hex_code} supprimé"}