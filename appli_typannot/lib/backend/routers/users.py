from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, File, UploadFile
from sqlmodel import Session, select
from typing import Annotated
from datetime import datetime
import os, uuid, shutil

from db import get_session, SessionDep
from models.user import User, UserCreate, UserUpdate, UserPublic, LoginRequest
from models.group import Group
from models.links import UserGroup, UserVideo, UserCurrentGroup
from models.video import Video, VideoPublic
from security import hash_password, verify_password, create_access_token, CurrentUser, SECRET_KEY, ALGORITHM
from fastapi.responses import FileResponse

VIDEOS_DIR = "videos_files"
os.makedirs(VIDEOS_DIR, exist_ok=True)

router = APIRouter(prefix="/users", tags=["Users"])

# =====================================================
# ROUTES UTILISATEURS
# =====================================================

@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED, summary="Créer un nouvel utilisateur")
def create_user(user: UserCreate, session: SessionDep):
    existing_user = session.exec(select(User).where(User.email == user.email)).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Un utilisateur avec l'email '{user.email}' existe déjà")
    hashed_pwd = hash_password(user.password)
    db_user = User(
        name=user.name,
        age=user.age,
        email=user.email,
        number=user.number,
        secret_name=user.secret_name,
        hashed_password=hashed_pwd
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    personal_group = Group(
        name=f"{db_user.name} (personnel)",
        description="Groupe personnel",
        is_personal=True,
        owner_user_id=db_user.id,
    )
    session.add(personal_group)
    session.commit()
    session.refresh(personal_group)

    link = UserGroup(user_id=db_user.id, group_id=personal_group.id)
    session.add(link)
    session.commit()

    current = UserCurrentGroup(user_id=db_user.id, group_id=personal_group.id)
    session.add(current)
    session.commit()

    return db_user

# LOGIN
@router.post("/login", tags=["Auth"], summary="Authentification utilisateur")
def login(data: LoginRequest, session: SessionDep):
    user = session.exec(select(User).where(User.email == data.email)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect")
    access_token = create_access_token(user_id=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "name": user.name
    }

# LIST USERS
@router.get("/", response_model=list[UserPublic], summary="Lister les utilisateurs")
def read_users(session: SessionDep, offset: int = Query(0), limit: int = Query(100), is_active: bool | None = Query(None)):
    query = select(User)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    total = len(session.exec(query).all())
    users = session.exec(query.offset(offset).limit(limit)).all()
    return users

# GET USER
@router.get("/{user_id}", response_model=UserPublic, summary="Obtenir un utilisateur par ID")
def read_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID '{user_id}' not found")
    return user

# UPDATE USER
@router.patch("/{user_id}", response_model=UserPublic, summary="Mettre à jour un utilisateur")
def update_user(user_id: int, user: UserUpdate, session: SessionDep):
    user_db = session.get(User, user_id)
    if not user_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")
    if user.email and user.email != user_db.email:
        existing = session.exec(select(User).where(User.email == user.email)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"The email address {user.email} is already in use")
    user_data = user.model_dump(exclude_unset=True)
    user_data['updated_at'] = datetime.utcnow()
    user_db.sqlmodel_update(user_data)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    return user_db

# DELETE USER
@router.delete("/{user_id}")
def delete_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")
    session.delete(user)
    session.commit()
    return {"ok": True, "message": f"User {user_id} successfully deleted"}

# TOGGLE ACTIVE
@router.patch("/{user_id}/toggle-active", response_model=UserPublic, summary="Activer/désactiver un utilisateur")
def toggle_user_active(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

# CURRENT GROUP
from models.group import CurrentGroupUpdate

@router.get("/{user_id}/current-group")
def get_current_group(user_id: int, session: SessionDep):
    row = session.get(UserCurrentGroup, user_id)
    if not row:
        return {"group_id": None}
    return {"group_id": row.group_id}

@router.put("/{user_id}/current-group")
def set_current_group(user_id: int, data: CurrentGroupUpdate, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    group = session.get(Group, data.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    link = session.exec(select(UserGroup).where((UserGroup.user_id == user_id) & (UserGroup.group_id == data.group_id))).first()
    if not link:
        raise HTTPException(status_code=403, detail="Utilisateur non membre de ce groupe")
    row = session.get(UserCurrentGroup, user_id)
    if row:
        row.group_id = data.group_id
        row.updated_at = datetime.utcnow()
    else:
        row = UserCurrentGroup(user_id=user_id, group_id=data.group_id)
    session.add(row)
    session.commit()
    return {"ok": True, "group_id": row.group_id}
