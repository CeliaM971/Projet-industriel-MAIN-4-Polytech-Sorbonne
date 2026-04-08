from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Annotated
from datetime import datetime
from typing import List, Dict, Any

from db import get_session, SessionDep
from models.group import Group, GroupCreate, GroupPublic, GroupUpdate
from models.user import User
from models.links import UserGroup
from security import CurrentUser

from sqlmodel import delete
from models.links import UserCurrentGroup, UserVideo, UserGroup
from models.video import Video
from models.invitation import GroupInvitation

from models.group import LeaveGroupRequest



import os

router = APIRouter(prefix="/groups", tags=["Groups"])

# =====================================================
# ROUTES GROUPES
# =====================================================

@router.post("/", response_model=GroupPublic, status_code=status.HTTP_201_CREATED)
def create_group_endpoint(group: GroupCreate, session: SessionDep, current_user: CurrentUser):
    # Créer le groupe
    db_group = Group(
        name=group.name,
        description=group.description,
        owner_user_id=current_user.id,
        is_personal=False
    )
    session.add(db_group)
    session.commit()
    session.refresh(db_group)

    # Ajouter le créateur dans UserGroup
    session.add(UserGroup(user_id=current_user.id, group_id=db_group.id))
    session.commit()

    return db_group


@router.get("/", response_model=list[GroupPublic], summary="Lister tous les groupes")
def list_groups(session: SessionDep):
    groups = session.exec(select(Group)).all()
    return groups

@router.get("/{group_id}", response_model=GroupPublic, summary="Obtenir un groupe par identifiant")
def get_group(group_id: int, session: SessionDep):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé")
    return group

@router.patch("/{group_id}", response_model=GroupPublic, summary="Modifier un groupe (owner uniquement)")
def update_group(group_id: int, group_update: GroupUpdate, session: SessionDep, current_user: CurrentUser):
    """
    Permet au propriétaire d'un groupe de modifier son nom et sa description.
    """
    # Vérifier que le groupe existe
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    
    # Vérifier que c'est un groupe partagé (pas personnel)
    if group.is_personal:
        raise HTTPException(status_code=403, detail="Impossible de modifier un groupe personnel")
    
    # Vérifier que l'utilisateur actuel est le propriétaire
    if group.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut modifier ce groupe")
    
    # Mettre à jour les champs fournis
    update_data = group_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="Aucune modification fournie")
    
    for key, value in update_data.items():
        setattr(group, key, value)
    
    session.add(group)
    session.commit()
    session.refresh(group)
    
    return group

# =====================================================
# ROUTES LIAISON UTILISATEUR / GROUPE
# =====================================================

@router.post("/{group_id}/users/{user_id}", status_code=status.HTTP_201_CREATED, summary="Ajouter un utilisateur à un groupe")
def add_user_to_group(group_id: int, user_id: int, session: SessionDep):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"L'utilisateur avec l'ID {user_id} n'a pas été trouvé")
    existing = session.exec(select(UserGroup).where((UserGroup.user_id == user_id) & (UserGroup.group_id == group_id))).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"L'Utilisateur {user_id} est deja dans le groupe {group_id}")
    link = UserGroup(user_id=user_id, group_id=group_id)
    session.add(link)
    session.commit()
    return {"ok": True, "message": f"Utilisateur {user_id} à été ajouté au groupe {group_id}"}

@router.get("/{group_id}/users", response_model=list[User], summary="Lister les utilisateurs d'un groupe")
def list_group_users(group_id: int, session: SessionDep):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Le groupe avec l'ID {group_id} n'a pas été trouvé")
    users = session.exec(select(User).join(UserGroup, UserGroup.user_id == User.id).where(UserGroup.group_id == group_id)).all()
    return users

@router.get("/users/{user_id}/groups", summary="Lister les groupes d'un utilisateur avec infos owner")
def list_user_groups(user_id: int, session: SessionDep) -> List[Dict[str, Any]]:
    """
    Retourne les groupes de l'utilisateur avec les informations du propriétaire.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"L'utilisateur avec l'ID {user_id} n'a pas été trouvé"
        )
    
    # Jointure avec User pour récupérer le nom de l'owner
    results = session.exec(
        select(Group, User)
        .join(UserGroup, UserGroup.group_id == Group.id)
        .outerjoin(User, User.id == Group.owner_user_id)  # LEFT JOIN pour avoir l'owner
        .where(UserGroup.user_id == user_id)
    ).all()
    
    groups_with_owner = []
    for group, owner in results:
        group_dict = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "created_at": group.created_at.isoformat(),
            "is_personal": group.is_personal,
            "owner_user_id": group.owner_user_id,
            "owner_name": owner.name if owner else None  # ✅ Nom de l'owner
        }
        groups_with_owner.append(group_dict)
    
    return groups_with_owner


def get_personal_group_id(session: SessionDep, user_id: int) -> int:
    group = session.exec(
        select(Group).where(
            (Group.is_personal == True) &
            (Group.owner_user_id == user_id)
        )
    ).first()

    if not group:
        raise HTTPException(500, "Groupe personnel introuvable")

    return group.id


def delete_group_impl(group: Group, session: SessionDep, current_user: CurrentUser):
    if group.is_personal:
        raise HTTPException(403, "Impossible de supprimer un groupe personnel")

    if group.owner_user_id != current_user.id:
        raise HTTPException(403, "Seul le propriétaire peut supprimer ce groupe")

    member_ids = session.exec(
        select(UserGroup.user_id).where(UserGroup.group_id == group.id)
    ).all()

    for uid in member_ids:
        current = session.get(UserCurrentGroup, uid)
        if current and current.group_id == group.id:
            current.group_id = get_personal_group_id(session, uid)
    
    videos = session.exec(
        select(Video).where(Video.group_id == group.id)
    ).all()

    video_ids = [v.id for v in videos if v.id is not None]

    for v in videos:
        try:
            if v.file_path and os.path.exists(v.file_path):
                os.remove(v.file_path)
        except Exception:
            pass

    if video_ids:
        session.exec(delete(UserVideo).where(UserVideo.video_id.in_(video_ids)))
    
    session.exec(delete(GroupInvitation).where(GroupInvitation.group_id == group.id))
    session.exec(delete(Video).where(Video.group_id == group.id))
    session.exec(delete(UserGroup).where(UserGroup.group_id == group.id))

    session.delete(group)
    session.commit()


@router.post("/{group_id}/leave", summary="Quitter un groupe (owner doit transférer)")
def leave_group(group_id: int, data: LeaveGroupRequest, session: SessionDep, current_user: CurrentUser):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")

    if group.is_personal:
        raise HTTPException(status_code=403, detail="Impossible de quitter le groupe personnel")

    membership = session.exec(
        select(UserGroup).where(
            (UserGroup.group_id == group_id) &
            (UserGroup.user_id == current_user.id)
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Vous n'êtes pas membre de ce groupe")

    # ✅ CAS OWNER : doit transférer avant de quitter
    if group.owner_user_id == current_user.id:
        if data is None or data.new_owner_user_id is None:
            raise HTTPException(
                status_code=400,
                detail="Owner doit fournir new_owner_user_id pour quitter sans supprimer"
            )

        if data.new_owner_user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Le nouvel owner doit être différent")

        new_owner_membership = session.exec(
            select(UserGroup).where(
                (UserGroup.group_id == group_id) &
                (UserGroup.user_id == data.new_owner_user_id)
            )
        ).first()

        if not new_owner_membership:
            raise HTTPException(status_code=400, detail="Le nouvel owner doit être membre du groupe")

        # transfert ownership
        group.owner_user_id = data.new_owner_user_id
        session.add(group)

    # quitter (supprimer le lien)
    session.delete(membership)

    # si groupe courant -> fallback sur groupe perso
    current = session.get(UserCurrentGroup, current_user.id)
    if current and current.group_id == group_id:
        current.group_id = get_personal_group_id(session, current_user.id)
        session.add(current)

    session.commit()
    return {"ok": True, "left_group": True, "transferred": (group.owner_user_id != current_user.id)}


@router.delete("/{group_id}", summary="Supprimer un groupe (owner uniquement)")
def delete_group(group_id: int, session: SessionDep, current_user: CurrentUser):
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Groupe introuvable")

    delete_group_impl(group, session, current_user)
    return {"ok": True}

@router.delete("/{group_id}/members/{user_id}", summary="Retirer un membre du groupe (owner uniquement)")
def remove_member_from_group(group_id: int, user_id: int, session: SessionDep, current_user: CurrentUser):
    """
    Permet au propriétaire d'un groupe de retirer un membre.
    Le membre ne peut pas être le propriétaire lui-même.
    """
    # Vérifier que le groupe existe
    group = session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Groupe introuvable")
    
    # Vérifier que c'est un groupe partagé (pas personnel)
    if group.is_personal:
        raise HTTPException(status_code=403, detail="Impossible de retirer des membres d'un groupe personnel")
    
    # Vérifier que l'utilisateur actuel est le propriétaire
    if group.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut retirer des membres")
    
    # Vérifier qu'on ne retire pas le propriétaire
    if user_id == group.owner_user_id:
        raise HTTPException(status_code=400, detail="Le propriétaire ne peut pas être retiré. Transférez d'abord la propriété.")
    
    # Vérifier que l'utilisateur à retirer existe
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Utilisateur {user_id} introuvable")
    
    # Vérifier que l'utilisateur est bien membre du groupe
    membership = session.exec(
        select(UserGroup).where(
            (UserGroup.group_id == group_id) &
            (UserGroup.user_id == user_id)
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="Cet utilisateur n'est pas membre du groupe")
    
    # Retirer le lien UserGroup
    session.delete(membership)
    
    # Si c'était son groupe courant, le remettre sur son groupe personnel
    current_group = session.get(UserCurrentGroup, user_id)
    if current_group and current_group.group_id == group_id:
        personal_group_id = get_personal_group_id(session, user_id)
        current_group.group_id = personal_group_id
        session.add(current_group)
    
    session.commit()
    
    return {
        "ok": True,
        "message": f"L'utilisateur {user.name} a été retiré du groupe {group.name}"
    }
