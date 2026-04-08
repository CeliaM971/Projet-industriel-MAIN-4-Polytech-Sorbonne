from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from db import SessionDep
from models.Annotation import (
    VideoAnnotation, AnnotationPath,
    AnnotationCreate, AnnotationUpdate, BulkAnnotationCreate,
    AnnotationWithPaths, AnnotationPathPublic, VideoAnnotationPublic
)
from models.video import Video
from security import CurrentUser

router = APIRouter(prefix="/annotations", tags=["Annotations"])


def _get_annotation_with_paths(annotation: VideoAnnotation, session) -> AnnotationWithPaths:
    """Utilitaire : construit un AnnotationWithPaths depuis une VideoAnnotation"""
    paths = session.exec(
        select(AnnotationPath)
        .where(AnnotationPath.annotation_id == annotation.id)
        .order_by(AnnotationPath.path_order)
    ).all()

    return AnnotationWithPaths(
        id=annotation.id,
        video_id=annotation.video_id,
        timestamp_ms=annotation.timestamp_ms,
        created_at=annotation.created_at,
        created_by=annotation.created_by,
        paths=[AnnotationPathPublic(**p.model_dump()) for p in paths],
    )


# =====================================================
# CRÉER UNE ANNOTATION (un seul timestamp)
# =====================================================
@router.post(
    "/videos/{video_id}/annotations",
    response_model=AnnotationWithPaths,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une annotation pour un timestamp d'une vidéo"
)
def create_annotation(
    video_id: int,
    data: AnnotationCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Vidéo {video_id} introuvable")

    annotation = VideoAnnotation(
        video_id=video_id,
        timestamp_ms=data.timestamp_ms,
        created_by=current_user.id,
    )
    session.add(annotation)
    session.commit()
    session.refresh(annotation)

    for path_in in data.paths:
        session.add(AnnotationPath(
            annotation_id=annotation.id,
            path_order=path_in.path_order,
            path_string=path_in.path_string,
        ))
    session.commit()

    return _get_annotation_with_paths(annotation, session)


# =====================================================
# ENVOYER TOUTES LES ANNOTATIONS D'UNE VIDÉO (bulk)
# Correspond au payload Flutter : {video_id, annotations: [...]}
# =====================================================
@router.post(
    "/videos/{video_id}/annotations/bulk",
    response_model=list[AnnotationWithPaths],
    status_code=status.HTTP_201_CREATED,
    summary="Envoyer toutes les annotations d'une vidéo d'un coup"
)
def bulk_create_annotations(
    video_id: int,
    data: BulkAnnotationCreate,
    session: SessionDep,
    current_user: CurrentUser,
):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Vidéo {video_id} introuvable")

    results = []
    for ann_in in data.annotations:
        annotation = VideoAnnotation(
            video_id=video_id,
            timestamp_ms=ann_in.timestamp_ms,
            created_by=current_user.id,
        )
        session.add(annotation)
        session.commit()
        session.refresh(annotation)

        for path_in in ann_in.paths:
            session.add(AnnotationPath(
                annotation_id=annotation.id,
                path_order=path_in.path_order,
                path_string=path_in.path_string,
            ))
        session.commit()

        results.append(_get_annotation_with_paths(annotation, session))

    return results


# =====================================================
# LISTER TOUTES LES ANNOTATIONS D'UNE VIDÉO
# =====================================================
@router.get(
    "/videos/{video_id}/annotations",
    response_model=list[AnnotationWithPaths],
    summary="Récupérer toutes les annotations d'une vidéo"
)
def list_annotations(video_id: int, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Vidéo {video_id} introuvable")

    annotations = session.exec(
        select(VideoAnnotation)
        .where(VideoAnnotation.video_id == video_id)
        .order_by(VideoAnnotation.timestamp_ms)
    ).all()

    return [_get_annotation_with_paths(a, session) for a in annotations]


# =====================================================
# RÉCUPÉRER UNE ANNOTATION PAR SON ID
# =====================================================
@router.get(
    "/annotations/{annotation_id}",
    response_model=AnnotationWithPaths,
    summary="Récupérer une annotation par son ID"
)
def get_annotation(annotation_id: int, session: SessionDep, current_user: CurrentUser):
    annotation = session.get(VideoAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} introuvable")

    return _get_annotation_with_paths(annotation, session)


# =====================================================
# MODIFIER UNE ANNOTATION
# =====================================================
@router.patch(
    "/annotations/{annotation_id}",
    response_model=AnnotationWithPaths,
    summary="Modifier une annotation (timestamp et/ou paths)"
)
def update_annotation(
    annotation_id: int,
    data: AnnotationUpdate,
    session: SessionDep,
    current_user: CurrentUser,
):
    annotation = session.get(VideoAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} introuvable")

    if annotation.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas l'auteur de cette annotation")

    if data.timestamp_ms is not None:
        annotation.timestamp_ms = data.timestamp_ms
        session.add(annotation)
        session.commit()

    # Si de nouveaux paths sont fournis, on supprime les anciens et on recrée
    if data.paths is not None:
        old_paths = session.exec(
            select(AnnotationPath).where(AnnotationPath.annotation_id == annotation_id)
        ).all()
        for p in old_paths:
            session.delete(p)
        session.commit()

        for path_in in data.paths:
            session.add(AnnotationPath(
                annotation_id=annotation_id,
                path_order=path_in.path_order,
                path_string=path_in.path_string,
            ))
        session.commit()

    return _get_annotation_with_paths(annotation, session)


# =====================================================
# SUPPRIMER UNE ANNOTATION
# =====================================================
@router.delete(
    "/annotations/{annotation_id}",
    status_code=status.HTTP_200_OK,
    summary="Supprimer une annotation et ses paths"
)
def delete_annotation(annotation_id: int, session: SessionDep, current_user: CurrentUser):
    annotation = session.get(VideoAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} introuvable")

    if annotation.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas l'auteur de cette annotation")

    # Supprimer les paths associés d'abord
    paths = session.exec(
        select(AnnotationPath).where(AnnotationPath.annotation_id == annotation_id)
    ).all()
    for p in paths:
        session.delete(p)
    session.commit()

    session.delete(annotation)
    session.commit()

    return {"ok": True, "message": f"Annotation {annotation_id} supprimée"}


# =====================================================
# SUPPRIMER TOUTES LES ANNOTATIONS D'UNE VIDÉO
# =====================================================
@router.delete(
    "/videos/{video_id}/annotations",
    status_code=status.HTTP_200_OK,
    summary="Supprimer toutes les annotations d'une vidéo"
)
def delete_all_annotations(video_id: int, session: SessionDep, current_user: CurrentUser):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Vidéo {video_id} introuvable")

    annotations = session.exec(
        select(VideoAnnotation).where(VideoAnnotation.video_id == video_id)
    ).all()

    for annotation in annotations:
        paths = session.exec(
            select(AnnotationPath).where(AnnotationPath.annotation_id == annotation.id)
        ).all()
        for p in paths:
            session.delete(p)
        session.delete(annotation)

    session.commit()
    return {"ok": True, "message": f"Toutes les annotations de la vidéo {video_id} supprimées"}