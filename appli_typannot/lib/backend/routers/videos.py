from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlmodel import Session, select
from typing import Annotated
import os
import shutil
import uuid
from fastapi.responses import FileResponse

from db import get_session, SessionDep
from models.video import Video, VideoPublic, VideoRename
from models.links import UserVideo
from models.user import User
from security import CurrentUser

router = APIRouter(prefix="/videos", tags=["Videos"])

VIDEOS_DIR = "videos_files"
os.makedirs(VIDEOS_DIR, exist_ok=True)

# =====================================================
# UPLOAD VIDEO
# =====================================================
@router.post("/users/{group_id}/videos/upload", response_model=VideoPublic, status_code=status.HTTP_201_CREATED, summary="Uploader une vidéo pour un groupe (authentification requise)")
def upload_video_for_group(
    group_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
):
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(VIDEOS_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_video = Video(
        title=title,
        description=description,
        file_path=file_path,
        group_id=group_id,
    )
    session.add(db_video)
    session.commit()
    session.refresh(db_video)

    user_video_link = UserVideo(
        user_id=current_user.id,
        video_id=db_video.id,
        is_owner=True
    )
    session.add(user_video_link)
    session.commit()

    return db_video

# =====================================================
# GRANT ACCESS
# =====================================================
@router.post("/{video_id}/grant-access/{user_id}", status_code=status.HTTP_201_CREATED, summary="Donner accès à une vidéo à un utilisateur")
def grant_video_access(video_id: int, user_id: int, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"La vidéo avec l'ID {video_id} n'a pas été trouvée")

    owner_link = session.exec(
        select(UserVideo).where((UserVideo.video_id == video_id) & (UserVideo.user_id == current_user.id) & (UserVideo.is_owner == True))
    ).first()
    if not owner_link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous n'êtes pas propriétaire de cette vidéo")

    from models.user import User
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"L'utilisateur avec l'ID {user_id} n'a pas été trouvé")

    existing = session.exec(
        select(UserVideo).where((UserVideo.user_id == user_id) & (UserVideo.video_id == video_id))
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"L'utilisateur {user_id} a déjà accès à cette vidéo")

    access_link = UserVideo(user_id=user_id, video_id=video_id, is_owner=False)
    session.add(access_link)
    session.commit()
    return {"ok": True, "message": f"Accès accordé à l'utilisateur {user_id} pour la vidéo {video_id}"}

# =====================================================
# LIST VIDEOS ACCESSIBLE
# =====================================================
@router.get("/my-videos", response_model=list[VideoPublic], summary="Lister mes vidéos accessibles")
def list_my_videos(session: SessionDep, current_user: CurrentUser):
    videos = session.exec(
        select(Video).join(UserVideo, UserVideo.video_id == Video.id).where(UserVideo.user_id == current_user.id)
    ).all()
    return videos

# =====================================================
# LIST VIDEOS BY GROUP
# =====================================================
@router.get("/groups/{group_id}/videos", response_model=list[VideoPublic], summary="Lister les vidéos d'un groupe")
def list_group_videos(group_id: int, session: SessionDep, current_user: CurrentUser):
    from models.links import UserGroup
    
    # Vérifier que l'utilisateur appartient au groupe
    membership = session.exec(
        select(UserGroup).where(
            (UserGroup.user_id == current_user.id) & 
            (UserGroup.group_id == group_id)
        )
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Vous n'êtes pas membre de ce groupe"
        )
    
    # Récupérer les vidéos du groupe
    videos = session.exec(
        select(Video).where(Video.group_id == group_id)
    ).all()
    
    return videos

# =====================================================
# DOWNLOAD VIDEO
# =====================================================
@router.get("/{video_id}/download", summary="Télécharger une vidéo (authentification requise)")
def download_video(video_id: int, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail=f"Vidéo {video_id} non trouvée en base")

    print(f"DEBUG file_path: {video.file_path}")
    print(f"DEBUG exists: {os.path.exists(video.file_path)}")
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"La vidéo avec l'ID {video_id} n'a pas été trouvée")

    access = session.exec(
        select(UserVideo).where((UserVideo.user_id == current_user.id) & (UserVideo.video_id == video_id))
    ).first()
    if not access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous n'avez pas accès à cette vidéo")

    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier vidéo introuvable sur le serveur")

    return FileResponse(path=video.file_path, media_type="video/mp4", filename=f"{video.title}.mp4")

# =====================================================
# RENAME VIDEO
# =====================================================
@router.patch("/{video_id}", response_model=VideoPublic, summary="Renommer une vidéo")
def rename_video(video_id: int, data: VideoRename, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"La video avec l'ID {video_id} n'a pas été trouvée")
    video.title = data.title
    session.add(video)
    session.commit()
    session.refresh(video)
    return video

# =====================================================
# DELETE VIDEO
# =====================================================
@router.delete("/{video_id}", status_code=status.HTTP_200_OK, summary="Supprimer une vidéo (propriétaire uniquement)")
def delete_video(video_id: int, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)


    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"La vidéo avec l'ID {video_id} n'a pas été trouvée")

    owner_link = session.exec(
        select(UserVideo).where((UserVideo.video_id == video_id) & (UserVideo.user_id == current_user.id) & (UserVideo.is_owner == True))
    ).first()
    if not owner_link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous n'êtes pas propriétaire de cette vidéo")

    try:
        if os.path.exists(video.file_path):
            os.remove(video.file_path)
    except Exception as e:
        print(f"Erreur suppression fichier vidéo: {e}")

    user_video_links = session.exec(select(UserVideo).where(UserVideo.video_id == video_id)).all()
    for link in user_video_links:
        session.delete(link)
    session.delete(video)
    session.commit()
    return {"ok": True, "message": f"Vidéo {video_id} supprimée"}
