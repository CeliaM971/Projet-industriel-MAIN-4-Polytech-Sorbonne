from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlmodel import Session, SQLModel, create_engine, select
from pydantic import BaseModel
from typing import Optional, List
import os

import mocap1 as mc
from AlphaPose import AlphaPose
from constants import Paths, MotionType

import cv2
import numpy as np

from models.video import Video

from db import lifespan, SessionDep
from routers import users_router, groups_router, videos_router, invitations_router, typannot_router, annotations_router

import json

app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(groups_router)
app.include_router(videos_router)
app.include_router(invitations_router)
app.include_router(typannot_router)      
app.include_router(annotations_router)

##### Helpers

# Mapping (limb, action) → MotionType used by plotAndExcelSave for axis labels / limits
MOTION_TYPE_MAP = {
    ("Head",     "Abduction/Adduction"): MotionType.HEAD_ABDADD.value,
    ("Head",     "Flexion/Extension"):   MotionType.HEAD_FLXEXT.value,
    ("Head",     "Rotation"):            MotionType.HEAD_ROTATION.value,
    ("Shoulder", "Abduction/Adduction"): MotionType.SHOULDER_ABDADD.value,
    ("Shoulder", "Flexion/Extension"):   MotionType.SHOULDER_FLXEXT.value,
    ("Torso",    "Abduction/Adduction"): MotionType.TORSO_ABDADD.value,
    ("Torso",    "Flexion/Extension"):   MotionType.TORSO_FLXEXT.value,
    ("Torso",    "Rotation"):            MotionType.TORSO_ROTATION.value,
    ("Arm",      "Abduction/Adduction"): MotionType.ARM_ABDADD.value,
    ("Arm",      "Flexion/Extension"):   MotionType.ARM_FLXEXT.value,
    ("Fore Arm", "Flexion/Extension"):   MotionType.FOREARM_FLXEXT.value,
}

def motion_data_to_lists(motion_data):
    """Convertit tous les éléments numpy en listes Python pour la sérialisation JSON."""
    result = []
    for item in motion_data:
        if hasattr(item, "tolist"):
            result.append(item.tolist())
        elif isinstance(item, list):
            result.append([float(v) if hasattr(v, "item") else v for v in item])
        else:
            result.append(item)
    return result

def generate_graphs_base64(
    plot_name: str,
    motion_data,
    video_path: str,
    motion_type: str,
    threshold_min: float,
    threshold_max: float,
    zoom_start: float,
    zoom_end: float,
    limit_min: float,
    limit_max: float,
    include_limit_of_data: bool,
    crop_coords: List[int],
) -> dict:
    """
    Appelle plotAndExcelSave (déjà dans mocap1.py) puis lit les PNG générés
    et les renvoie encodés en base64.
    Retourne un dict {"graph": "...", "graph_velocity": "..."}.
    """
    # Valeurs y min/max pour les lignes de référence
    angles_array = np.array(motion_data[1])
    y_max = float(np.max(angles_array)) if len(angles_array) > 0 else 0.0
    y_min = float(np.min(angles_array)) if len(angles_array) > 0 else 0.0

    cropped_video_name = os.path.splitext(os.path.basename(video_path))[0]

    _, paths = mc.plotAndExcelSave(
        plot_name=plot_name,
        cropped_video_name=cropped_video_name,
        plot_color=np.array([0, 114, 189]),   # bleu matplotlib classique
        motion_data=motion_data,
        filename=video_path,
        coordA1=tuple(crop_coords[:2]) if len(crop_coords) >= 2 else (0, 0),
        coordA2=tuple(crop_coords[2:4]) if len(crop_coords) >= 4 else (0, 0),
        y_max=y_max,
        y_min=y_min,
        motion_type=motion_type,
        is_limit_option_selected=include_limit_of_data,
        limit_max=limit_max if limit_max is not None else -1000,
        limit_min=limit_min if limit_min is not None else -1000,
        zoom_start=zoom_start if zoom_start is not None else -1,
        zoom_end=zoom_end if zoom_end is not None else -1,
        threshold_max=threshold_max if threshold_max is not None else -1000,
        threshold_min=threshold_min if threshold_min is not None else -1000,
    )

    # paths[0] = courbe angle, paths[1] = fichier excel (pas utile ici)
    # La courbe vitesse est sauvegardée dans le dossier "Vitesse" à côté
    plot_path = paths[0]

    # Chemin du graphique vitesse : même dossier parent + NomVitesse/...resPlotV.png
    tps = f"{float(motion_data[0][0])}-{float(motion_data[0][-1])}"
    velocity_plot_path = os.path.join(
        os.path.dirname(os.path.dirname(plot_path)),
        f"{plot_name}Vitesse",
        f"{tps}resPlotV.png"
    )

    result = {}

    # Encodage base64 du graphique d'angles
    if os.path.exists(plot_path):
        with open(plot_path, "rb") as f:
            result["graph"] = base64.b64encode(f.read()).decode("utf-8")
    else:
        result["graph"] = None

    # Encodage base64 du graphique de vitesse
    if os.path.exists(velocity_plot_path):
        with open(velocity_plot_path, "rb") as f:
            result["graph_velocity"] = base64.b64encode(f.read()).decode("utf-8")
    else:
        result["graph_velocity"] = None

    return result



##### Skeleton analysis

class AnalysisRequest(BaseModel):
    video_id: int  # ID of the video in the databse
    model: str
    limb: str
    action: str
    start_time: float
    end_time: float
    frame_rate: int
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    zoom_start: Optional[float] = None
    zoom_end: Optional[float] = None
    limit_min: Optional[float] = None
    limit_max: Optional[float] = None
    delete_last_slices: bool
    include_limit_of_data: bool
    crop_coords: List[int]
    username: str

@app.post("/api/analyze")
async def analyze_video(request: AnalysisRequest, session: SessionDep):
    try:
        # Recup the video from the database
        video = session.get(Video, request.video_id)
        if not video:
            raise HTTPException(
                status_code=404,
                detail=f"Vidéo avec l'ID {request.video_id} introuvable"
            )
        
        # Use the path of the file in the database
        video_path = video.file_path
        
        # Check that the file really exist
        if not os.path.exists(video_path):
            raise HTTPException(
                status_code=404,
                detail=f"Fichier vidéo introuvable sur le serveur: {video_path}"
            )
        
        if request.start_time >= request.end_time:
            raise HTTPException(
                status_code=400,
                detail="Le temps de fin doit être supérieur au temps de début"
            )
        
        if request.end_time - request.start_time < 1:
            raise HTTPException(
                status_code=400,
                detail="L'analyse doit porter sur au moins 1 seconde"
            )
        
        listErr = []
        motion_data = None
        skip_motion_processing = False
        
        if request.model == "AlphaPose" and request.limb == "Head":
            if request.action == "Abduction/Adduction":
                listErr, motion_data = mc.extractgraphs_ap_abd_add(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            elif request.action == "Flexion/Extension":
                listErr, motion_data = mc.extractgraphs_ap_nodding(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            elif request.action == "Rotation":
                listErr, motion_data = mc.extractgraphs_ap_rotation(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
        
        elif request.model == "AlphaPose" and request.limb == "Shoulder":
            if request.action == "Abduction/Adduction":
                listErr, motion_data = mc.extractgraphs_ap_abd_add_shoul(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            elif request.action == "Flexion/Extension":
                listErr, motion_data = mc.extractgraphs_ap_shrugging(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Combinaison non supportée: {request.model} + {request.limb} + {request.action}"
                )

        
        elif request.model == "AlphaPose" and request.limb == "Torso":
            if request.action == "Abduction/Adduction":
                listErr, motion_data = mc.extractgraphs_ap_buste_abd_add(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            elif request.action == "Flexion/Extension":
                listErr, motion_data = mc.extractgraphs_ap_buste_flexion(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            elif request.action == "Rotation":
                listErr, motion_data = mc.extractgraphs_ap_buste_rotation(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
        
        elif request.model == "AlphaPose" and request.limb == "Arm":
            if request.action == "Abduction/Adduction":
                listErr, motion_data = mc.extractgraphs_ap_arm_abduction(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            elif request.action == "Flexion/Extension":
                listErr, motion_data = mc.extractgraphs_ap_arm_flexion(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Combinaison non supportée: {request.model} + {request.limb} + {request.action}"
                )

        
        elif request.model == "AlphaPose" and request.limb == "Fore Arm":
            if request.action == "Flexion/Extension":
                listErr, motion_data = mc.extractgraphs_ap_forearm_flexion(
                    video_path, request.start_time, request.end_time,
                    request.frame_rate, request.crop_coords, skip_motion_processing, request.username
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Combinaison non supportée: {request.model} + {request.limb} + {request.action}"
                )

        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Combinaison non supportée: {request.model} + {request.limb} + {request.action}"
            )
        
        if motion_data is None or len(motion_data) == 0:
            raise HTTPException(
                status_code=500,
                detail=f"Le modèle {request.model} n'a pas retourné de résultats"
            )
        
        if request.limit_min is not None or request.limit_max is not None:
            limit_min = request.limit_min if request.limit_min is not None else float('-inf')
            limit_max = request.limit_max if request.limit_max is not None else float('inf')
            motion_data = mc.apply_limit_to_data(motion_data, limit_min, limit_max)
        
        return {
            "success": True,
            "message": "Analyse terminée avec succès",
            "data": {
                "missing_joints": listErr,
                "time_series": motion_data[0] if len(motion_data) > 0 else [],
                "angles": motion_data[1:] if len(motion_data) > 1 else [],
                "analysis_type": f"{request.limb}_{request.action}",
                "model_used": request.model,
                "video_id": request.video_id,
                "video_title": video.title
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        print(f"Erreur lors de l'analyse: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse: {str(e)}"
        )

@app.get("/api/analysis-status")
async def get_analysis_status():
    """Obtenir le statut de l'analyse en cours"""
    return {
        "current_step": mc.current_analysis_step if hasattr(mc, 'current_analysis_step') else "En attente"
    }

##### Gestionnaires d'erreurs

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Gestionnaire d'erreurs global"""
    print(f"Erreur non gérée: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


with open('../config.json') as f:
    config = json.load(f)

SERVER_ADDRESS = f"{config['server_ip']}:{config['server_port']}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host= config['server_ip'],
        port=config['server_port'],
        reload=True,
        log_level="info"
    )
