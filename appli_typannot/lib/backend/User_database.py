from typing import Annotated
from datetime import datetime
from contextlib import asynccontextmanager
from passlib.context import CryptContext
from fastapi.responses import JSONResponse
from fastapi import APIRouter

from fastapi import Depends, FastAPI, HTTPException, Query, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, Session, SQLModel, create_engine, select
from pydantic import EmailStr, field_validator
import re

import bcrypt
import os
import uuid
import shutil
import hashlib


from datetime import timedelta
from jose import JWTError, jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials




pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


class UserBase(SQLModel):
    name: str = Field(index=True)
    age: int | None = Field(default=None, index=True)
    email: EmailStr = Field(index=True, unique=True)  # Validation email automatique
    number: str = Field(min_length=10, max_length=15)



class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    secret_name: str
    hashed_password: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)


class UserPublic(UserBase):
    id: int
    is_active: bool


class UserCreate(UserBase):
    secret_name: str
    password: str = Field(min_length=6, max_length=200)


class UserUpdate(SQLModel):
    name: str | None = None
    age: int | None = None
    email: EmailStr | None = None
    number: str | None = None
    secret_name: str | None = None
    is_active: bool | None = None


class UserListResponse(SQLModel):
    users: list[UserPublic]
    total: int #nombre total d'utilisateurs dans la base
    offset: int #nombre d'éléments sautés
    limit: int #nombre maximum d'éléments retournés

class LoginRequest(SQLModel):
    email: EmailStr
    password: str = Field(max_length=200)
    
# =====================================================
# CLASSES GROUPES & VIDEOS
# =====================================================

class GroupBase(SQLModel):
    name: str = Field(index=True)
    description: str | None = None


class Group(GroupBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_personal: bool = Field(default=False, index=True)   # True = groupe perso
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)


class GroupPublic(GroupBase):
    id: int
    created_at: datetime
    is_personal: bool
    owner_user_id: int | None


class GroupCreate(GroupBase):
    pass


class VideoBase(SQLModel):
    title: str = Field(index=True)
    description: str | None = None 
    file_path: str  #chemin serveur de la vidéo (pas le chemin de l'routerareil local)


class Video(VideoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id")   #chaque vidéo routerartient à un groupe
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VideoPublic(VideoBase):
    id: int
    group_id: int
    created_at: datetime


class VideoCreate(SQLModel):
    title: str
    description: str | None = None
    group_id: int


class UserCurrentGroup(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id")
    updated_at: datetime = Field(default_factory=datetime.utcnow)



def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec bcrypt directement.
    Utilise SHA-256 pour les mots de passe > 72 bytes.
    """
    # Convertir en bytes
    password_bytes = password.encode('utf-8')
    
    # Si trop long, pré-hasher avec SHA-256
    if len(password_bytes) > 72:
        password_bytes = hashlib.sha256(password_bytes).digest()
    
    # Hasher avec bcrypt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie un mot de passe contre son hash.
    """
    # Convertir en bytes
    password_bytes = plain_password.encode('utf-8')
    
    # Appliquer la même transformation
    if len(password_bytes) > 72:
        password_bytes = hashlib.sha256(password_bytes).digest()
    
    # Vérifier avec bcrypt
    return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(router: FastAPI):
    # Startup
    print("Démarrage...")
    create_db_and_tables()
    yield
    # Shutdown
    print("Arrêt...")


# =====================================================
# APPLICATION FASTAPI
# =====================================================

router = APIRouter(
    #prefix="/users",
    #tags=["users"]
)



# dossier ou stocker les vidéos importées
VIDEOS_DIR = "videos_files"
os.makedirs(VIDEOS_DIR, exist_ok=True)

# =====================================================
# ROUTES API
# =====================================================

@router.get("/", tags=["Root"])
def read_root():
    """Page d'accueil de l'API"""
    return {
        "message": "API Gestion Utilisateurs",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "create_user": "POST /users/",
            "list_users": "GET /users/",
            "get_user": "GET /users/{user_id}",
            "update_user": "PATCH /users/{user_id}",
            "delete_user": "DELETE /users/{user_id}",
            "search_users": "GET /users/search/"
        }
    }


###
@router.post(
    "/users/",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
    summary="Créer un nouvel utilisateur"
)
def create_user(user: UserCreate, session: SessionDep):
    """
    Crée un nouveau utilisateur avec mot de passe hashé.
    
    - **nom**: Nom (2-100 caractères)
    - **email**: Email unique
    - **numéro**: Numéro de téléphone (10-15 caractères)
    - **mot de passe**: Mot de passe (6-200 caractères)
    """
    # Vérifier si l'email existe déjà
    existing_user = session.exec(
        select(User).where(User.email == user.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un utilisateur avec l'email '{user.email}' existe déjà"
        )
    
    # Hasher le mot de passe
    try:
        hashed_pwd = hash_password(user.password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors du hashage du mot de passe: {str(e)}"
        )
    
    # Créer utilisateur
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
#=================================================
     #Créer le groupe personnel
    personal_group = Group(
        name=f"{db_user.name} (personnel)",
        description="Groupe personnel",
        is_personal=True,
        owner_user_id=db_user.id,
    )
    session.add(personal_group)
    session.commit()
    session.refresh(personal_group)

    #Lier l’utilisateur à son groupe personnel
    link = UserGroup(
        user_id=db_user.id,
        group_id=personal_group.id
    )
    session.add(link)
    session.commit()


    current = UserCurrentGroup(
        user_id=db_user.id,
        group_id=personal_group.id
    )
    session.add(current)
    session.commit()


#========================================================

    return db_user

class UserGroup(SQLModel, table=True):
    
    ##Table de liaison Utilisateur / Groupe 
    ##Un utilisateur peut routerartenir à plusieurs groupes
    ##Un groupe peut contenir plusieurs utilisateurs
    
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    group_id: int = Field(foreign_key="group.id", primary_key=True)
    joined_at: datetime = Field(default_factory=datetime.utcnow)

#class LoginRequest(SQLModel):
 #   email: EmailStr
  #  password: str
    
    
@router.post("/login", tags=["Auth"], summary="Authentification utilisateur")
def login(data: LoginRequest, session: SessionDep):
    """Authentifie un utilisateur et retourne un token JWT"""
    user = session.exec(
        select(User).where(User.email == data.email)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé"
        )

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect"
        )

    access_token = create_access_token(user_id=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "name": user.name,
        "user_id": user.id
    }




   


"""@router.post("/login")
def login(data: LoginRequest, session: SessionDep):
    user = session.exec(
        select(User).where(User.email == data.email)
    ).first()

    if not user:
        raise HTTPException(401, "Incorrect email or password")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")

    return {"message": "Authentication successful", "user_id": user.id}

"""

@router.get("/users/", response_model=UserListResponse, summary="List all users")
def read_users(
    session: SessionDep,
    offset: int = Query(default=0, ge=0, description="Nombre d'éléments à sauter"),
    limit: int = Query(default=100, ge=1, le=100, description="Nombre max d'éléments"),
    is_active: bool | None = Query(default=None, description="Filtrer par statut actif")
):
    """Récupère une liste paginée d'utilisateurs"""
    query = select(User)
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    total = len(session.exec(query).all())

    users = session.exec(
        query.offset(offset).limit(limit)
    ).all()
    
    return UserListResponse(
        users=users,
        total=total,
        offset=offset,
        limit=limit
    )

@router.get(
    "/users/search/",
    response_model=list[UserPublic],
    summary="Search for users"
)
def search_users(
    session: SessionDep,
    email: str | None = Query(default=None, description="Rechercher par email"),

):

    query = select(User)
    
    if email:
        query = query.where(User.email.ilike(f"%{email}%"))

    
    users = session.exec(query).all()
    return users



@router.get("/users/{user_id}", response_model=UserPublic, summary="Obtain a user by ID")
def read_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID '{user_id}' not found")
    return user


@router.patch("/users/{user_id}", response_model=UserPublic, summary="Update user")
def update_user(user_id: int, user: UserUpdate, session: SessionDep):
    user_db = session.get(User, user_id)
    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Vérifier email unique si modifié
    if user.email and user.email != user_db.email:
        existing = session.exec(
            select(User).where(User.email == user.email)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The email address {user.email} is already in use"
            )
    user_data = user.model_dump(exclude_unset=True)
    user_data['updated_at'] = datetime.utcnow()  # Mettre à jour le timestamp
    user_db.sqlmodel_update(user_data)
    session.add(user_db)
    session.commit()
    session.refresh(user_db)
    return user_db


@router.delete("/users/{user_id}")
def delete_user(user_id: int, session: SessionDep):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    session.delete(user)
    session.commit()
    return {"ok": True, "message": f"User {user_id} successfully deleted"}


@router.patch(
    "/users/{user_id}/toggle-active",
    response_model=UserPublic,
    tags=["Users"],
    summary="Activer/désactiver un utilisateur"
)
def toggle_user_active(user_id: int, session: SessionDep):
    """
    Bascule le statut actif/inactif d'un utilisateur 
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow()
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user

# =====================================================
# ROUTES GROUPES
# =====================================================

@router.post(
    "/groups/",
    response_model=GroupPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un groupe"
)
def create_group_endpoint(group: GroupCreate, session: SessionDep):
    db_group = Group(
        name=group.name,
        description=group.description,
    )
    session.add(db_group)
    session.commit()
    session.refresh(db_group)
    return db_group


@router.get(
    "/groups/",
    response_model=list[GroupPublic],
    summary="Lister tous les groupes"
)
def list_groups(session: SessionDep):
    groups = session.exec(select(Group)).all()
    return groups


@router.get(
    "/groups/{group_id}",
    response_model=GroupPublic,
    summary="Obtenir un groupe par identifiant"
)
def get_group(group_id: int, session: SessionDep):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé"
        )
    return group

# =====================================================
# ROUTES LIAISON UTILISATEUR / GROUPE
# =====================================================

@router.post(
    "/groups/{group_id}/users/{user_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter un utilisateur à un groupe"
)
def add_user_to_group(
    group_id: int,
    user_id: int,
    session: SessionDep,
):
    #vérifie que le groupe existe
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé",
        )

    # verifie que l'utilisateur existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"L'utilisateur avec l'ID {user_id} n'a pas été trouvé",
        )

    #vérifie si l'utilisateur est déjà dans le groupe
    existing = session.exec(
        select(UserGroup).where(
            (UserGroup.user_id == user_id) &
            (UserGroup.group_id == group_id)
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"L'Utilisateur {user_id} est deja dans le groupe {group_id}",
        )

    link = UserGroup(user_id=user_id, group_id=group_id)
    session.add(link)
    session.commit()

    return {"ok": True, "message": f"Utilisateur {user_id} à été ajouté au groupe {group_id}"}


@router.get(
    "/groups/{group_id}/users",
    response_model=list[UserPublic],
    summary="Lister les utilisateurs d'un groupe"
)
def list_group_users(group_id: int, session: SessionDep):
    # Vérifier que le groupe existe
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé",
        )

    users = session.exec(
        select(User)
        .join(UserGroup, UserGroup.user_id == User.id)
        .where(UserGroup.group_id == group_id)
    ).all()

    return users


@router.get(
    "/users/{user_id}/groups",
    response_model=list[GroupPublic],
    summary="Lister les groupes d'un utilisateur"
)
def list_user_groups(user_id: int, session: SessionDep):
    # Vérifier que l'utilisateur existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"L'utilisateur avec l'ID {user_id} n'a pas été trouvé",
        )

    groups = session.exec(
        select(Group)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .where(UserGroup.user_id == user_id)
    ).all()

    return groups
    
    
# =====================================================
# ROUTES VIDEOS
# =====================================================
"""
@router.post(
    "/groups/{group_id}/videos/upload",
    response_model=VideoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Uploader une vidéo pour un groupe"
)
def upload_video_for_group(
    group_id: int,
    session: SessionDep,
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    
):
    # Vérifier que le groupe existe
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé",
        )

    # Générer un nom de fichier unique
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(VIDEOS_DIR, filename)

    # Sauvegarder le fichier sur le serveur
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Créer l'entrée en base
    db_video = Video(
        title=title,
        description=description,
        file_path=file_path,
        group_id=group_id,
    )
    session.add(db_video)
    session.commit()
    session.refresh(db_video)

    return db_video
    """

@router.get(
    "/groups/{group_id}/videos",
    response_model=list[VideoPublic],
    summary="Lister les vidéos d'un groupe"
)
def list_group_videos(group_id: int, session: SessionDep):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé",
        )

    videos = session.exec(
        select(Video).where(Video.group_id == group_id)
    ).all()
    
    return videos

class VideoRename(SQLModel):
    title: str


@router.delete(
    "/videos/{video_id}",
    status_code=status.HTTP_200_OK,
    summary="Supprimer une vidéo"
)
def delete_video(video_id: int, session: SessionDep):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La video avec l'ID {video_id} n'a pas été trouvée",
        )

    try:
        if os.path.exists(video.file_path):
            os.remove(video.file_path)
    except Exception as e:
        print(f"Erreur suppression fichier vidéo: {e}")

    session.delete(video)
    session.commit()
    return {
        "ok": True,
        "message": f"Video {video_id} supprimée"
    }
    

"===================================================================="

class CurrentGroupUpdate(SQLModel):
    group_id: int

#Récupérer le current group
@router.get("/users/{user_id}/current-group")
def get_current_group(user_id: int, session: SessionDep):
    row = session.get(UserCurrentGroup, user_id)
    if not row:
        return {"group_id": None}
    return {"group_id": row.group_id}

#Modifier / set le current group 
@router.put("/users/{user_id}/current-group")
def set_current_group(user_id: int, data: CurrentGroupUpdate, session: SessionDep):
    # (optionnel) vérifier que user existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # vérifier que groupe existe
    group = session.get(Group, data.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")

    # vérifier que user appartient au groupe
    link = session.exec(
        select(UserGroup).where(
            (UserGroup.user_id == user_id) &
            (UserGroup.group_id == data.group_id)
        )
    ).first()
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


# Configuration JWT
SECRET_KEY = "votre_cle_secrete_ultra_securisee_a_changer"  # À changer en production !
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 jours

security = HTTPBearer()

def create_access_token(user_id: int) -> str:
    """Crée un token JWT pour un utilisateur"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "user_id": user_id,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

from fastapi import Header

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: SessionDep
) -> User:
    """Récupère l'utilisateur authentifié depuis le token JWT"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré"
        )
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé"
        )
    
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

#============= INVITATIONS ===================================================

@router.get("/me/invitations")
def my_invitations(session: SessionDep, current_user: CurrentUser):
    invs = session.exec(
        select(GroupInvitation).where(
            (GroupInvitation.invitee_email == current_user.email) &
            (GroupInvitation.status == "pending")
        )
    ).all()
    return invs

class GroupInvitation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="group.id", index=True)
    inviter_user_id: int = Field(foreign_key="user.id", index=True)

    invitee_email: EmailStr = Field(index=True)
    status: str = Field(default="pending", index=True)  # pending/accepted/declined
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InviteRequest(SQLModel):
    email: EmailStr

@router.post("/groups/{group_id}/invite")
def invite_to_group(group_id: int, data: InviteRequest, session: SessionDep, current_user: CurrentUser):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Groupe introuvable")
    if group.is_personal:
        raise HTTPException(403, "Invitations interdites sur un groupe personnel")

    #vérifier que l’inviteur est membre du groupe
    member = session.exec(select(UserGroup).where(
        (UserGroup.group_id == group_id) & (UserGroup.user_id == current_user.id)
    )).first()
    if not member:
        raise HTTPException(403, "Vous n'êtes pas membre de ce groupe")

    # (optionnel) éviter doublon d’invitation pending
    existing = session.exec(select(GroupInvitation).where(
        (GroupInvitation.group_id == group_id) &
        (GroupInvitation.invitee_email == data.email) &
        (GroupInvitation.status == "pending")
    )).first()
    if existing:
        raise HTTPException(409, "Invitation déjà envoyée")

    inv = GroupInvitation(
        group_id=group_id,
        inviter_user_id=current_user.id,
        invitee_email=data.email
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)
    return inv


class InvitationDecision(SQLModel):
    decision: str  # "accepted" ou "declined"


@router.post("/invitations/{inv_id}/respond")
def respond_invitation(inv_id: int, data: InvitationDecision, session: SessionDep, current_user: CurrentUser):
    inv = session.get(GroupInvitation, inv_id)
    if not inv:
        raise HTTPException(404, "Invitation introuvable")
    if inv.invitee_email != current_user.email:
        raise HTTPException(403, "Ce n'est pas votre invitation")

    if data.decision not in ["accepted", "declined"]:
        raise HTTPException(400, "Décision invalide")

    inv.status = data.decision
    session.add(inv)

    # si accepté → ajouter UserGroup
    if data.decision == "accepted":
        existing = session.exec(select(UserGroup).where(
            (UserGroup.user_id == current_user.id) & (UserGroup.group_id == inv.group_id)
        )).first()
        if not existing:
            session.add(UserGroup(user_id=current_user.id, group_id=inv.group_id))

    session.commit()
    return {"ok": True, "status": inv.status}


#===============================================================================
@router.patch(
    "/videos/{video_id}",
    response_model=VideoPublic,
    summary="Renommer une vidéo"
)
def rename_video(video_id: int, data: VideoRename, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La video avec l'ID {video_id} n'a pas été trouvée",
        )

    video.title = data.title
    session.add(video)
    session.commit()
    session.refresh(video)
    return video
    

# MODIFIER LA ROUTE LOGIN pour retourner un token
@router.post("/login", tags=["Auth"], summary="Authentification utilisateur")
def login(data: LoginRequest, session: SessionDep):
    """Authentifie un utilisateur et retourne un token JWT"""
    user = session.exec(
        select(User).where(User.email == data.email)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé"
        )

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect"
        )

    # Créer le token JWT
    access_token = create_access_token(user_id=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "name": user.name
    }


# NOUVELLE TABLE pour lier les utilisateurs aux vidéos
class UserVideo(SQLModel, table=True):
    """Table de liaison Utilisateur / Vidéo
    Un utilisateur peut avoir accès à plusieurs vidéos
    Une vidéo peut être accessible par plusieurs utilisateurs
    """
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    video_id: int = Field(foreign_key="video.id", primary_key=True)
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    is_owner: bool = Field(default=False)  # True si c'est l'uploader de la vidéo


# MODIFIER LA ROUTE UPLOAD pour associer l'utilisateur
@router.post(
    "/users/{group_id}/videos/upload",
    response_model=VideoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Uploader une vidéo pour un groupe (authentification requise)"
)
def upload_video_for_group(
    group_id: int,
    session: SessionDep,
    current_user: CurrentUser,  # ← Authentification requise
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
):
    # Vérifier que le groupe existe
    """
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé",
        )"""

    # Générer un nom de fichier unique
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(VIDEOS_DIR, filename)

    # Sauvegarder le fichier sur le serveur
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Créer l'entrée en base
    db_video = Video(
        title=title,
        description=description,
        file_path=file_path,
        group_id=group_id,
    )
    session.add(db_video)
    session.commit()
    session.refresh(db_video)

    # Associer l'utilisateur comme propriétaire de la vidéo
    user_video_link = UserVideo(
        user_id=current_user.id,
        video_id=db_video.id,
        is_owner=True
    )
    session.add(user_video_link)
    session.commit()

    return db_video


# ROUTE pour donner accès à une vidéo à un autre utilisateur
@router.post(
    "/videos/{video_id}/grant-access/{user_id}",
    status_code=status.HTTP_201_CREATED,
    summary="Donner accès à une vidéo à un utilisateur"
)
def grant_video_access(
    video_id: int,
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Permet au propriétaire d'une vidéo de donner accès à d'autres utilisateurs"""
    
    # Vérifier que la vidéo existe
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La vidéo avec l'ID {video_id} n'a pas été trouvée"
        )
    
    # Vérifier que l'utilisateur actuel est propriétaire
    owner_link = session.exec(
        select(UserVideo).where(
            (UserVideo.video_id == video_id) &
            (UserVideo.user_id == current_user.id) &
            (UserVideo.is_owner == True)
        )
    ).first()
    
    if not owner_link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas propriétaire de cette vidéo"
        )
    
    # Vérifier que l'utilisateur cible existe
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"L'utilisateur avec l'ID {user_id} n'a pas été trouvé"
        )
    
    # Vérifier si l'accès n'existe pas déjà
    existing = session.exec(
        select(UserVideo).where(
            (UserVideo.user_id == user_id) &
            (UserVideo.video_id == video_id)
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"L'utilisateur {user_id} a déjà accès à cette vidéo"
        )
    
    # Créer l'accès
    access_link = UserVideo(
        user_id=user_id,
        video_id=video_id,
        is_owner=False
    )
    session.add(access_link)
    session.commit()
    
    return {
        "ok": True,
        "message": f"Accès accordé à l'utilisateur {user_id} pour la vidéo {video_id}"
    }


# ROUTE SÉCURISÉE pour lister les vidéos accessibles par l'utilisateur
@router.get(
    "/my-videos",
    response_model=list[VideoPublic],
    summary="Lister mes vidéos accessibles"
)
def list_my_videos(
    session: SessionDep,
    current_user: CurrentUser,
):
    """Liste toutes les vidéos auxquelles l'utilisateur a accès"""
    videos = session.exec(
        select(Video)
        .join(UserVideo, UserVideo.video_id == Video.id)
        .where(UserVideo.user_id == current_user.id)
    ).all()
    
    return videos


# ROUTE SÉCURISÉE pour télécharger une vidéo
#from fastapi.responses import FileResponseGmail 
from fastapi.responses import FileResponse



@router.get(
    "/videos/{video_id}/download",
    summary="Télécharger une vidéo (authentification requise)"
)
def download_video(
    video_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Télécharge une vidéo si l'utilisateur y a accès"""
    
    # Vérifier que la vidéo existe
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La vidéo avec l'ID {video_id} n'a pas été trouvée"
        )
    
    # Vérifier que l'utilisateur a accès
    access = session.exec(
        select(UserVideo).where(
            (UserVideo.user_id == current_user.id) &
            (UserVideo.video_id == video_id)
        )
    ).first()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cette vidéo"
        )
    
    # Vérifier que le fichier existe
    if not os.path.exists(video.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier vidéo introuvable sur le serveur"
        )
    
    return FileResponse(
        path=video.file_path,
        media_type="video/mp4",
        filename=f"{video.title}.mp4"
    )


# MODIFIER LA ROUTE DELETE pour vérifier la propriété
@router.delete(
    "/videos/{video_id}",
    status_code=status.HTTP_200_OK,
    summary="Supprimer une vidéo (propriétaire uniquement)"
)
def delete_video(
    video_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Supprime une vidéo si l'utilisateur en est propriétaire"""
    
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La vidéo avec l'ID {video_id} n'a pas été trouvée"
        )
    
    # Vérifier que l'utilisateur est propriétaire
    owner_link = session.exec(
        select(UserVideo).where(
            (UserVideo.video_id == video_id) &
            (UserVideo.user_id == current_user.id) &
            (UserVideo.is_owner == True)
        )
    ).first()
    
    if not owner_link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas propriétaire de cette vidéo"
        )
    
    # Supprimer le fichier
    try:
        if os.path.exists(video.file_path):
            os.remove(video.file_path)
    except Exception as e:
        print(f"Erreur suppression fichier vidéo: {e}")
    
    # Supprimer les accès
    session.exec(
        select(UserVideo).where(UserVideo.video_id == video_id)
    ).all()
    
    # Supprimer la vidéo
    session.delete(video)
    session.commit()
    
    return {
        "ok": True,
        "message": f"Vidéo {video_id} supprimée"
    }
    
app = FastAPI(lifespan=lifespan)

app.include_router(router)
    
# =====================================================
# POINT D'ENTRÉE
# =====================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "User_database:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload en dev
        log_level="info"
    )

