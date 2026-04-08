from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class VideoAnnotation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="video.id")
    timestamp_ms: int                # ex: 37000 pour t=37s
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: int = Field(foreign_key="user.id")

class AnnotationPath(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    annotation_id: int = Field(foreign_key="videoannotation.id")
    path_order: int                  # ordre dans savedPaths (0, 1, 2...)
    path_string: str                 # ex: "Membre sup›Selec D›Epaule›Flx/Ext›Flexion›2/4"

# --- Schémas Pydantic pour l'API ---

class AnnotationPathPublic(SQLModel):
    id: int
    annotation_id: int
    path_order: int
    path_string: str

class VideoAnnotationPublic(SQLModel):
    id: int
    video_id: int
    timestamp_ms: int
    created_at: datetime
    created_by: int

# --- Schémas pour créer / modifier ---

class PathIn(SQLModel):
    path_order: int
    path_string: str                 # ex: "Membre sup›Selec D›Epaule›Flx/Ext›Flexion›2/4"

class AnnotationCreate(SQLModel):
    timestamp_ms: int
    paths: list[PathIn]

class AnnotationUpdate(SQLModel):
    timestamp_ms: int | None = None
    paths: list[PathIn] | None = None  # si fourni, remplace tous les paths existants

class BulkAnnotationCreate(SQLModel):
    """Pour envoyer toutes les annotations d'une vidéo d'un coup depuis Flutter"""
    video_id: int
    annotations: list[AnnotationCreate]

class AnnotationWithPaths(SQLModel):
    """Annotation complète avec ses paths, pour la réponse GET"""
    id: int
    video_id: int
    timestamp_ms: int
    created_at: datetime
    created_by: int
    paths: list[AnnotationPathPublic]