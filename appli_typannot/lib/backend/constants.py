import os
import sys

from enum import Enum
from typing import Final

# Pose Estimation Models
class PoseModel(Enum):
    ALPHA_POSE = 0
    MM_POSE = 1
    REP_NET = 2

# Video Player States
class VideoState(Enum):
    PAUSED = 0
    PLAYING = 1

# Video Player Modes
class VideoMode(Enum):
    FULL = 0
    CROPPED = 1

# Paths to folders
class Paths:
    # Determine the application path
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        APP: Final = sys._MEIPASS
    else:
        # Running as a normal Python script
        APP: Final = os.path.dirname(os.path.abspath(__file__))
    
    ASSETS_GUI: Final = os.path.join(APP, "assets", "gui1_assets")
    ASSETS_FONT: Final = os.path.join(APP, "assets", "rambaultbolditalic.ttf")
    ASSETS_RSA_KEY: Final = os.path.join(APP, "assets", "rsaclewindowsssh")
    DATA: Final = os.path.join(APP, "data")
    DATA_IMS: Final = os.path.join(APP, "data", "ims")
    DATA_IMS_STOCK: Final = os.path.join(APP, "data", "ims_old")
    DATA_BUFFER: Final = os.path.join(APP, "data", "buffer.mp4")
    # To avoid the results getting deleted after closing the app
    # Put them in the USER's home directory
    USER_HOME: Final = os.path.join(os.path.expanduser("~"), "Body-to-Text_results")
    RESULTS: Final = os.path.join(USER_HOME)
    RESULTS_RES: Final = os.path.join(USER_HOME, "server_output")
    RESULTS_RESULTS: Final = os.path.join(USER_HOME, "results")

# Motion Type IDs
class MotionType(Enum):
    HEAD_ABDADD = 11
    HEAD_FLXEXT = 12
    HEAD_ROTATION = 13
    HEAD_ROT_LAT = 14
    SHOULDER_ABDADD = 21
    SHOULDER_FLXEXT = 22
    TORSO_ABDADD = 31
    TORSO_FLXEXT = 32
    TORSO_ROTATION = 33
    ARM_ABDADD = 41
    ARM_FLXEXT = 42
    ARM_FLXEXT_LAT = 43
    FOREARM_FLXEXT = 51

# Y-Axis Labels
class YAxisLabel(Enum):
    ROTATION =  "<< Left         Angle [deg]       Right >>"
    FLXEXT =    "<< Flex         Angle norm          Ext >>"
    SHRUGGING = "|| Normal                    Haussement >>"
    ABDADD =    "<< Abduction     Distance     Adduction >>"
    ANGLE =     "<<              Angle [deg]             >>"

# Standalone constants

# Maximum duration of the video clip in seconds
MAX_CLIP_LENGTH: Final = 60 * 5  # 5 minutes
