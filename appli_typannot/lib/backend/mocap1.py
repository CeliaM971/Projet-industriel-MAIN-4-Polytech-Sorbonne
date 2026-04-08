# Standard library imports
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
from copy import copy

# Third-party imports
import cv2
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import numpy.linalg as la
import pandas as pd
import paramiko
import xlsxwriter as xls
from PIL import Image
from scp import SCPClient

# Configure matplotlib to use Agg backend (no GUI)
matplotlib.use("Agg")

# Local imports
from AlphaPose import AlphaPose
from MMPose import MMPose
from datetime import datetime

from constants import PoseModel, Paths, MotionType, YAxisLabel

KEY_PATH = ""
IP_ADRESS = ""
USER = ""
PASS_PHRASE = ""

stopCalcule = False
current_analysis_step = ""  # Global variable to track the current analysis step for logging in the GUI

################################################################################
############################## Code MOCAP Original #############################
################################################################################

def runserver(username, pose, processing_chunk_counter):
    global current_analysis_step
    try:
        start_time = datetime.now()
        print(f"Starting server connection at {start_time.strftime('%H:%M:%S')}")
        if username == "":
            username = "default"
        print(f"Connecting to server as {username}...", end=" ", flush=True)
        current_analysis_step = "Connecting to server..."
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=IP_ADRESS,
            username=USER,
            key_filename= os.path.expanduser(KEY_PATH),
            passphrase=PASS_PHRASE,
        )
        print("Connected")
        
        print("Setting up directories...", end=" ", flush=True)
        current_analysis_step = "Setting up directories..."
        if processing_chunk_counter == 0:
            pass
            # First create the directory if it doesn't exist
            _, stdout, _ = ssh.exec_command(
                f"mkdir -p /home/main4_2526/server/cluster/server_output"
            )
            stdout.channel.recv_exit_status()
            # Then empty it by removing all contents
            _, stdout, _ = ssh.exec_command(
                f"rm -rf /home/main4_2526/server/cluster/server_output/*"
            )
            # First create the directory if it doesn't exist
            _, stdout, _ = ssh.exec_command(
                f"mkdir -p /home/main4_2526/server/cluster/ims"
            )
            stdout.channel.recv_exit_status()
            # Then empty it by removing all contents
            _, stdout, _ = ssh.exec_command(
                f"rm -rf /home/main4_2526/server/cluster/ims/*"
            )
            stdout.channel.recv_exit_status()
        print("Directories set up")

        print("Sending images to server...", end=" ", flush=True)
        current_analysis_step = "Sending images to server..."
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(
                Paths.DATA_IMS, f"/home/main4_2526/server/cluster", recursive=True
            )
        print("Images sent")
        
        print("Running pose estimation", end=" ", flush=True)
        current_analysis_step = "Running pose estimation..."
        if pose == PoseModel.ALPHA_POSE:
            pass
            print("on AlphaPose...", end=" ", flush=True)
            _, stdout, stderr = ssh.exec_command(
                f"source ~/miniconda3/etc/profile.d/conda.sh; "
                f"conda activate alphapose;"
                f"cd /home/main4_2526/server/cluster/; "
                #f"conda run -n alphapose -v --cwd alphapose "
                f"python3 /home/main4_2526/server/cluster/scripts/demo_inference.py --cfg /home/main4_2526/server/cluster/configs/coco/resnet/256x192_res50_lr1e-3_1x.yaml --checkpoint pretrained_models/fast_res50_256x192.pth --indir /home/main4_2526/server/cluster/ims/ --outdir /home/main4_2526/server/cluster/server_output/ --format cmu --posebatch 1 --detbatch 1 --vis_fast;"
            )
            
            print("STDERR:\n", stderr.read().decode())
            stdout.channel.recv_exit_status()
        elif pose == PoseModel.MM_POSE:
            print("on MMPose...", end=" ", flush=True)
            _, stdout, _ = ssh.exec_command(f"\
                source miniconda3/etc/profile.d/conda.sh;\
                export CUDA_VISIBLE_DEVICES='' ;\
                conda run -n openmmlab -v --cwd /home/lexikhum/LEXIKHUM \
                python ./mmpose/demo/inferencer_demo.py --pose2d human --pred-out-dir user/{username}/res1 user/{username}/ims/"
            )
            stdout.channel.recv_exit_status()
            _, stdout, _ = ssh.exec_command(
                f"python3 /home/lexikhum/LEXIKHUM/convert_mmpose_to_json.py '/home/lexikhum/LEXIKHUM/user/{username}/res1' '{username}' {str(processing_chunk_counter)}"
            )
            stdout.channel.recv_exit_status()
            _, stdout, _ = ssh.exec_command(
                f"rm -rf /home/lexikhum/LEXIKHUM/user/{username}/res1"
            )
            stdout.channel.recv_exit_status()
        elif pose == PoseModel.REP_NET:
            print("on RepNet...", end=" ", flush=True)
            _, stdout, _ = ssh.exec_command(
                f"source miniconda3/etc/profile.d/conda.sh; conda run -n repnet -v --cwd /home/lexikhum/LEXIKHUM/6DRepNet/ python3 test.py /home/lexikhum/LEXIKHUM/user/{username}/ims/ {username} {str(processing_chunk_counter)}"
            )
            stdout.channel.recv_exit_status()
            _, stdout, _ = ssh.exec_command(
                f"mv /home/lexikhum/LEXIKHUM/user/{username}/res/* /home/lexikhum/LEXIKHUM/user/{username}/server_output"
            )
            stdout.channel.recv_exit_status()
            _, stdout, _ = ssh.exec_command(
                f"rm -rf /home/lexikhum/LEXIKHUM/user/{username}/res"
            )
        print("Pose estimation completed")

        print("Receiving results from server...", end=" ", flush=True)
        current_analysis_step = "Receiving results from server..."
        with SCPClient(ssh.get_transport()) as scp:
            scp.get(
                f"/home/main4_2526/server/cluster/server_output",
                Paths.RESULTS,
                recursive=True,
            )
        print("Results received")

        current_analysis_step = "Done !"
        end_time = datetime.now()
        elapsed_seconds = (end_time - start_time).total_seconds()
        print(f"Server connection completed at {end_time.strftime('%H:%M:%S')}")
        print(f"Total elapsed time: {int(elapsed_seconds // 60)} minutes {int(elapsed_seconds % 60)} seconds")
        
    except Exception as e:
        print(f"Error during server connection: {e}")
    finally:
        ssh.close()

def dist2point2D(x1, y1, x2, y2):
    return pow(pow(x1 - x2, 2) + pow(y1 - y2, 2), 1 / 2)

def dist2points2D(A, B):
    return pow(pow(A[0] - B[0], 2) + pow(A[1] - B[1], 2), 1 / 2)

def angle_between_points(p2, p1, p3):
    """Calculates the angle in degrees between three points."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    dx1 = x1 - x2
    dy1 = y1 - y2
    dx2 = x3 - x2
    dy2 = y3 - y2
    angle1 = math.atan2(dy1, dx1)
    angle2 = math.atan2(dy2, dx2)
    angle = math.degrees(angle2 - angle1)
    if angle < 0:
        angle += 360
    return angle

def getAngle(a, b, c):
    vector_1 = [c[0] - a[0], c[1] - a[1]]

    vector_2 = [b[0] - a[0], b[1] - a[1]]

    a = np.array(vector_1)
    b = np.array(vector_2)
    inner = np.inner(a, b)
    norms = la.norm(a) * la.norm(b)
    if abs(norms) < 1e-10:  # Avoid division by zero
        norms = 1e-10 * (1 if norms > 0 else -1)
    cos = inner / norms
    rad = np.arccos(np.clip(cos, -1.0, 1.0))
    deg = np.rad2deg(rad)

    return deg

def getAngleVec(u, v):
    # Calcul de la norme des vecteurs
    norme_u = math.sqrt(sum([x**2 for x in u]))
    norme_v = math.sqrt(sum([x**2 for x in v]))
    normMului = norme_u * norme_v
    # Calcul du produit scalaire
    produit_scalaire = sum([u[i] * v[i] for i in range(len(u))])

    # Calcul de l'angle en radians
    if abs(normMului) < 1e-10:  # Avoid division by zero
        normMului = 1e-10 * (1 if normMului > 0 else -1)
    if produit_scalaire / normMului > 1:
        angle = math.acos(1)
    elif produit_scalaire / normMului < -1:
        angle = math.acos(-1)
    else:
        angle = math.acos(produit_scalaire / normMului)

    deg = np.rad2deg(angle)

    return deg

def vecteurCord(point1, point2):
    x1, y1 = point1
    x2, y2 = point2
    vecteur = [x2 - x1, y2 - y1]
    return vecteur

def getAngleVecNega(vecteur1, vecteur2):
    # Calculer le produit scalaire des deux vecteurs
    produit_scalaire = sum(x * y for x, y in zip(vecteur1, vecteur2))

    # Calculer les normes des vecteurs
    norme1 = math.sqrt(sum(x**2 for x in vecteur1))
    norme2 = math.sqrt(sum(x**2 for x in vecteur2))

    # Calculer l'angle en radians en utilisant la fonction acos
    denominator = norme1 * norme2
    if abs(denominator) < 1e-10:  # Avoid division by zero
        denominator = 1e-10 * (1 if denominator > 0 else -1)
    if produit_scalaire / denominator > 1:
        angle_radians = math.acos(1)
    elif produit_scalaire / denominator < -1:
        angle_radians = math.acos(-1)
    else:
        angle_radians = math.acos(produit_scalaire / denominator)

    # Convertir l'angle en degrés
    angle_degres = math.degrees(angle_radians)

    # Déterminer le sens de rotation
    # Calculer le déterminant entre les vecteurs
    determinant = vecteur1[0] * vecteur2[1] - vecteur1[1] * vecteur2[0]

    # Si le déterminant est négatif, inverser le signe de l'angle
    if determinant < 0:
        angle_degres = -angle_degres

    # Retourner l'angle calculé
    return angle_degres

def filtreMoyenneur1D(data, taille):
    if taille % 2 == 0:
        taille += 1
    demiTaille = int(taille / 2)
    for i in range(demiTaille, len(data) - demiTaille):
        data[i] = np.mean(data[(i - demiTaille) : (i + demiTaille + 1)])
    return data

def DeleteImsJson():
    vers = platform.system()
    print(Paths.RESULTS)
    result_path = os.path.join(Paths.RESULTS, 'res1', 'alphapose-results.json')
    if vers == "Linux" or vers == "Darwin":
        os.system(f"rm -d -r {Paths.DATA_IMS}")
        if not stopCalcule:
            os.system(f"rm -d -r {result_path}")
    if vers == "Windows":
        os.system(f"del /Q {Paths.DATA_IMS}")
        if not stopCalcule:
            os.system(f"del /Q {result_path}")

def DeleteAllInFile(repertoire):
    files = os.listdir(repertoire)
    for i in range(0, len(files)):
        print("files", files[i])
        path = os.path.join(repertoire, files[i])
        try:
            shutil.rmtree(path)
        except:
            os.remove(path)

def deleteJpgExcel(Path):
    os.remove(Path[0])
    os.remove(Path[1])

def apply_limit_to_data(motion_data, limit_min, limit_max):
    clipped_values = np.clip(motion_data[1], limit_min, limit_max)
    return [motion_data[0], clipped_values]

def get_frame_rate(filename):
    if not os.path.exists(filename):
        sys.stderr.write("ERROR: filename %r was not found!" % (filename,))
        return -1
    try:
        out = subprocess.check_output(
            [
            "ffprobe",
            "-v", "0",  # Suppress unnecessary output
            "-select_streams", "v",  # Select video stream
            "-print_format", "flat",  # Output in flat format
            "-show_entries", "stream=r_frame_rate",  # Get frame rate
            filename
            ],
            stderr=subprocess.PIPE  # Redirect stderr to prevent output to console
        )
        output_str = out.decode("utf-8").strip()

        # Handle different possible output formats
        if '"' in output_str:
            # Original expected format: stream.r_frame_rate="30/1"
            rate_str = output_str.split('"')[1]
        else:
            # Alternative format: may not have quotes or might have a different structure
            rate_str = output_str.split('=')[-1].strip()
            # Remove any quotes that might be around the value
            rate_str = rate_str.strip('"\'')

        if '/' in rate_str:
            num, denom = rate_str.split('/')
            denominator = float(denom)
            if abs(denominator) < 1e-10:  # Avoid division by zero
                denominator = 1e-10 * (1 if denominator > 0 else -1)
            return float(num) / denominator
        else:
            return float(rate_str)
    except (subprocess.SubprocessError, ValueError, IndexError) as e:
        sys.stderr.write(f"ERROR: Unable to determine frame rate for {filename}: {e}\n")
        # Try an alternative approach using cv2
        try:
            cap = cv2.VideoCapture(filename)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                cap.release()
                if fps > 0:
                    return fps
        except Exception as e2:
            sys.stderr.write(f"ERROR: Alternative frame rate detection failed: {e2}\n")
        return 30.0  # Default frame rate as fallback

def dirNumberMax(path):
    try:
        files = os.listdir(path)
    except:
        files = next(os.walk(path))[1]

    numbers = []
    for filename in files:
        matches = re.findall(r"(/d+)", filename)
        if matches:
            numbers.append(int(matches[0]))
        else:
            numbers.append(0)
    return max(numbers) if numbers else 0

def dirNumber(path):
    max_value = 0
    file_count = 0
    
    for filename in os.listdir(path):
        file_count += 1
        if filename.endswith(".jpg"):
            try:
                file_number = int(filename.replace(".jpg", ""))
                if file_number > max_value:
                    max_value = file_number
            except ValueError:
                # Skip files that don't convert to integers
                pass
                
    return max_value, file_count

def has_bilateral_data(motion_type):
    bilateral_motion_types = [
        MotionType.SHOULDER_FLXEXT.value,
        MotionType.ARM_ABDADD.value,
        MotionType.ARM_FLXEXT.value,
        MotionType.ARM_FLXEXT_LAT.value,
        MotionType.FOREARM_FLXEXT.value
    ]
    return motion_type in bilateral_motion_types

def plotAndExcelSave(
        plot_name,
        cropped_video_name,
        plot_color,
        motion_data,
        filename,
        coordA1,
        coordA2,
        y_max,
        y_min,
        motion_type,
        is_limit_option_selected,
        limit_max,
        limit_min,
        zoom_start,
        zoom_end,
        threshold_max,
        threshold_min,
    ):
    _, ax = plt.subplots()

    # Plot the data
    if has_bilateral_data(motion_type):
        plt.plot(motion_data[0], motion_data[1], c=plot_color / 350.0, label="Droit", linewidth=2)
        inverted_plot_color = np.array([255, 255, 255]) - plot_color
        plt.plot(motion_data[0], motion_data[2], c=inverted_plot_color / 350.0, label="Gauche", linewidth=2)
    else:
        plt.plot(motion_data[0], motion_data[1], c=plot_color / 255.0, label="Data", linewidth=2)

    # Limit lines
    if limit_max != -1000 and limit_min != -1000:
        limit_max_local = limit_max
        limit_min_local = limit_min
    else:
        if motion_type == MotionType.HEAD_ABDADD.value:
            limit_max_local = 60
            limit_min_local = -60
        elif motion_type == MotionType.HEAD_FLXEXT.value \
        or motion_type == MotionType.HEAD_ROTATION.value:
            limit_max_local = 0.5
            limit_min_local = -0.5
        elif motion_type == MotionType.SHOULDER_ABDADD.value \
        or motion_type == MotionType.SHOULDER_FLXEXT.value \
        or motion_type == MotionType.TORSO_ABDADD.value:
            limit_max_local = 1
            limit_min_local = -0
        elif motion_type == MotionType.HEAD_ROT_LAT.value \
        or motion_type == MotionType.TORSO_FLXEXT.value:
            limit_max_local = 50
            limit_min_local = -50
        elif motion_type == MotionType.TORSO_ROTATION.value:
            limit_max_local = 3
            limit_min_local = -3
        elif motion_type == MotionType.ARM_ABDADD.value \
        or motion_type == MotionType.ARM_FLXEXT.value \
        or motion_type == MotionType.ARM_FLXEXT_LAT.value \
        or motion_type == MotionType.FOREARM_FLXEXT.value:
            limit_max_local = 180
            limit_min_local = -0

    # Additional horizontal line and label for the Y axis
    if motion_type == MotionType.HEAD_ABDADD.value:
        ax.set_ylabel(YAxisLabel.ROTATION.value)
        plt.axhline(y=0, color="black", linestyle="dashed", label="ligne 0°,position neutre")
    elif motion_type == MotionType.HEAD_FLXEXT.value:
        ax.set_ylabel(YAxisLabel.FLXEXT.value)
        plt.axhline(y=0, color="black", linestyle="--", label="neutre")
    elif motion_type == MotionType.HEAD_ROTATION.value:
        ax.set_ylabel(YAxisLabel.ROTATION.value)
        plt.axhline(y=0, color="black", linestyle="dashed", label="ligne 0° ,Rotation neutre")
    elif motion_type == MotionType.HEAD_ROT_LAT.value:
        ax.set_ylabel(YAxisLabel.FLXEXT.value)
        plt.axhline(y=0, color="black", linestyle="--", label="ligne neutre 0°")
    elif motion_type == MotionType.SHOULDER_ABDADD.value:
        min_display_angle = min(y_min, limit_min_local)
        ax.set_ylabel(YAxisLabel.ABDADD.value)
        plt.axhline(y=min_display_angle, color="black", linestyle="dashed")
    elif motion_type == MotionType.SHOULDER_FLXEXT.value:
        min_display_angle = min(y_min, limit_min_local)
        ax.set_ylabel(YAxisLabel.SHRUGGING.value)
        plt.axhline(y=min_display_angle, color="black", linestyle="dashed")
    elif motion_type == MotionType.TORSO_ABDADD.value:
        ax.set_ylabel(YAxisLabel.ROTATION.value)
        plt.axhline(y=0, color="black", linestyle="--", label="ligne neutre 0°")
    elif motion_type == MotionType.TORSO_FLXEXT.value:
        ax.set_ylabel(YAxisLabel.FLXEXT.value)
        plt.axhline(y=1,color='lime',linestyle='solid',label='hyper extension')
    elif motion_type == MotionType.TORSO_ROTATION.value:
        ax.set_ylabel(YAxisLabel.ROTATION.value)
        plt.axhline(y=0, color="black", linestyle="--", label="ligne neutre 0°")
    elif motion_type == MotionType.ARM_ABDADD.value:
        ax.set_ylabel(YAxisLabel.ANGLE.value)
        plt.axhline(y=90, color="black", linestyle="dashed", label="ligne neutre")
    elif motion_type == MotionType.ARM_FLXEXT.value:
        min_display_angle = min(y_min, limit_min_local)
        ax.set_ylabel(YAxisLabel.ANGLE.value)
        plt.axhline(y=min_display_angle, color="black", linestyle="dashed", label="ligne 0° neutre")
    elif motion_type == MotionType.ARM_FLXEXT_LAT.value:
        ax.set_ylabel(YAxisLabel.ANGLE.value)
        plt.axhline(y=0, color="black", linestyle="dashed", label="ligne 0° neutre")
    elif motion_type == MotionType.FOREARM_FLXEXT.value:
        ax.set_ylabel(YAxisLabel.ANGLE.value)

    # Zoom handling
    if zoom_start != -1 or zoom_end != -1:
        # If only one of the zoom values was set, use fallback values
        if zoom_start == -1:
            zoom_start = motion_data[0][-1]
        if zoom_end == -1:
            zoom_end = motion_data[0][0]
        ax.set_xlim(zoom_end, zoom_start)

    # Threshold handling
    if threshold_max != -1000:
        plt.axhline(y=threshold_max, color="red", linestyle="--", label="Threshold max")
    if threshold_min != -1000:
        plt.axhline(y=threshold_min, color="pink", linestyle="--", label="Threshold min")

    # Rest of the plot
    if is_limit_option_selected:
        plt.axhline(y=max(y_max, limit_max_local), color="lime", linestyle="solid")
        plt.axhline(y=min(y_min, limit_min_local), color="blue", linestyle="solid")
    ax.set_xlabel("Temps [s]")
    plt.legend()
    plt.suptitle(f"Courbe {plot_name} [Coordonnées cadre: {coordA1}, {coordA2}]", color=plot_color / 255.0,)
    plt.title(f"Video : {os.path.basename(filename)}", c=plot_color / 400.0, fontsize=8)

    plot_dir = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        plot_name
    )
    if not os.path.isdir(plot_dir):
        os.makedirs(plot_dir)

    tps = f"{float(motion_data[0][0])}-{float(motion_data[0][-1])}"
    plot_path = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        plot_name,
        tps + "resPlot.png"
    )
    plt.savefig(plot_path)

    time_column_name = "Temps[s]"
    if has_bilateral_data(motion_type):
        value_column_name = plot_name + " Droit [deg]"
        value_column_name_bis = plot_name + " Gauche [deg]"
        data = pd.DataFrame({time_column_name: motion_data[0], value_column_name: motion_data[1], value_column_name_bis: motion_data[2]})
    else:
        value_column_name = plot_name + " [deg]"
        data = pd.DataFrame({time_column_name: motion_data[0], value_column_name: motion_data[1]})

    excel_file_path = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        "resExcel.xlsx"
    )
    start_time = float(motion_data[0][0])
    end_time = float(motion_data[0][-1])
    current_sheet_name = f"Sheet {start_time}-{end_time}"
    if os.path.exists(excel_file_path):
        try:
            excel_file = pd.read_excel(excel_file_path, sheet_name=current_sheet_name, index_col=0)
            change = False
            
            # Create a new dataframe for our data
            velocity_dataframe = pd.DataFrame()
            
            # First add the time column
            velocity_dataframe[time_column_name] = motion_data[0]
            
            # Copy over existing columns that we're not replacing
            for column in excel_file.columns:
                if column == time_column_name or column == value_column_name:
                    continue
                if has_bilateral_data(motion_type):
                    if column == value_column_name_bis:
                        continue
                velocity_dataframe[column] = excel_file[column].values
            
            # Add our new data columns
            velocity_dataframe[value_column_name] = motion_data[1]
            change = True
            if has_bilateral_data(motion_type):
                velocity_dataframe[value_column_name_bis] = motion_data[2]

            # Use the new dataframe
            if change:
                data = velocity_dataframe
            
            with pd.ExcelWriter(excel_file_path, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
                data.to_excel(writer, sheet_name=current_sheet_name)
        except Exception as e:
            print(f"Error, Excel processing failed: {e}")
            # Fallback to creating a new file if there was an error
            xls.Workbook(excel_file_path)
            data.to_excel(excel_file_path, sheet_name=current_sheet_name, index=False)
    else:
        xls.Workbook(excel_file_path)
        data.to_excel(excel_file_path, sheet_name=current_sheet_name, index=False)

    velocity_plot_dir = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        f"{plot_name}Vitesse"
    )
    if not os.path.exists(velocity_plot_dir):
        os.makedirs(velocity_plot_dir)
    _, ax2 = plt.subplots()

    if has_bilateral_data(motion_type):
        copied = copy(motion_data)
        for i in range(len(copied[1]) - 1):
            denominator = (motion_data[0][i + 1] - motion_data[0][i])
            if abs(denominator) < 1e-10:  # Avoid division by zero
                denominator = 1e-10 * (1 if denominator > 0 else -1)
            copied[1][i] = abs(motion_data[1][i + 1] - motion_data[1][i]) / denominator
            copied[2][i] = abs(motion_data[2][i + 1] - motion_data[2][i]) / denominator
        copied[1][len(copied[1]) - 1] = copied[1][len(copied[1]) - 2]
        copied[2][len(copied[2]) - 1] = copied[2][len(copied[2]) - 2]

        time_points_data = copied[0]
        velocity_data = copied[1]
        velocity_data_bis = copied[2]
        velocity_data = filtreMoyenneur1D(velocity_data, 7)
        velocity_data_bis = filtreMoyenneur1D(velocity_data_bis, 7)

        plt.plot(time_points_data, velocity_data, c=plot_color / 350.0, label="Droit", linewidth=2)
        inverted_plot_color = np.array([255, 255, 255]) - plot_color
        plt.plot(time_points_data, velocity_data_bis, c=inverted_plot_color / 350.0, label="Gauche", linewidth=2)
    else:
        copied = copy(motion_data)
        for i in range(len(copied[1]) - 1):
            denominator = (motion_data[0][i + 1] - motion_data[0][i])
            if abs(denominator) < 1e-10:  # Avoid division by zero
                denominator = 1e-10 * (1 if denominator > 0 else -1)
            copied[1][i] = abs(motion_data[1][i + 1] - motion_data[1][i]) / denominator
        copied[1][len(copied[1]) - 1] = copied[1][len(copied[1]) - 2]

        time_points_data = copied[0]
        velocity_data = copied[1]
        velocity_data = filtreMoyenneur1D(velocity_data, 15)

        plt.plot(time_points_data, velocity_data, c=plot_color / 255.0, label="Data", linewidth=2)

    # Zoom handling
    if zoom_start != -1 or zoom_end != -1:
        # If only one of the zoom values was set, use fallback values
        if zoom_start == -1:
            zoom_start = motion_data[0][-1]
        if zoom_end == -1:
            zoom_end = motion_data[0][0]
        ax2.set_xlim(zoom_end, zoom_start)

    ax2.set_ylabel("Vitesse [*/s]  *:deg ou vitesse normalisée")
    ax2.set_xlabel("Temps [s]")
    plt.legend(loc="best")
    plt.suptitle("Courbe vitesse " + plot_name, c=plot_color / 255.0)
    velocity_plot_dir = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        f"{plot_name}Vitesse"
    )
    if not os.path.exists(velocity_plot_dir):
        os.makedirs(velocity_plot_dir)
    velocity_plot_path = os.path.join(velocity_plot_dir, f"{tps}resPlotV.png")
    plt.savefig(velocity_plot_path)

    time_column_name = "Temps[s]"
    if has_bilateral_data(motion_type):
        value_column_name = f"Vitesse {plot_name} Droit [*/s]"
        value_column_name_bis = f"Vitesse {plot_name} Gauche [*/s]"
        data = pd.DataFrame({
            time_column_name: time_points_data,
            value_column_name: velocity_data,
            value_column_name_bis: velocity_data_bis
        })
    else:
        value_column_name = f"Vitesse {plot_name} [*/s]"
        data = pd.DataFrame({
            time_column_name: time_points_data,
            value_column_name: velocity_data
        })

    velocity_excel_path = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        "resExcelV.xlsx"
    )

    if os.path.exists(velocity_excel_path):
        try:
            excel_file = pd.read_excel(velocity_excel_path, sheet_name=current_sheet_name, index_col=0)
            
            velocity_dataframe = pd.DataFrame()
            velocity_dataframe[time_column_name] = time_points_data
            
            # Copy over existing columns that we're not replacing
            for column in excel_file.columns:
                if column == time_column_name or column == value_column_name:
                    continue
                if has_bilateral_data(motion_type):
                    if column == value_column_name_bis:
                        continue
                velocity_dataframe[column] = excel_file[column].values

            # Add our new velocity data columns
            if has_bilateral_data(motion_type):
                velocity_dataframe[value_column_name] = velocity_data
                velocity_dataframe[value_column_name_bis] = velocity_data_bis
                change = True
            else:
                velocity_dataframe[value_column_name] = velocity_data
                change = True
            
            # Use the new dataframe
            if change:
                data = velocity_dataframe
                
            with pd.ExcelWriter(
                velocity_excel_path, mode="a", engine="openpyxl", if_sheet_exists="replace"
            ) as writer:
                data.to_excel(writer, sheet_name=current_sheet_name)
        except Exception as e:
            print(f"Error, Excel velocity processing error: {e}")
            # Fallback to creating a new file if there was an error
            xls.Workbook(velocity_excel_path)
            data.to_excel(velocity_excel_path, sheet_name=current_sheet_name, index=False)
    else:
        xls.Workbook(velocity_excel_path)
        data.to_excel(velocity_excel_path, sheet_name=current_sheet_name, index=False)

    result_directory = os.path.join(
        Paths.RESULTS_RESULTS,
        os.path.basename(filename),
        cropped_video_name,
        plot_name
    )
    _, nb = dirNumber(result_directory)

    return nb, [plot_path, excel_file_path]

def FusionImage(Path1, Path2, plot_name, numMax, video_name, cropped_video_name, tps):
    # First check if both source files exist
    if not os.path.exists(Path1):
        print(f"Warning: Source plot file not found: {Path1}")
        return
    
    if not os.path.exists(Path2):
        print(f"Warning: Source velocity plot file not found: {Path2}")
        return
        
    # Charger les images à fusionner
    image1 = Image.open(Path1)
    image2 = Image.open(Path2)

    # Calculer la largeur et la hauteur de l'image finale
    largeur_totale = image1.width + image2.width
    hauteur_max = max(image1.height, image2.height)

    # Créer une nouvelle image avec les dimensions appropriées
    fused_picture = Image.new("RGB", (largeur_totale, hauteur_max))

    # Copier la première image à gauche
    fused_picture.paste(image1, (0, 0))

    # Copier la deuxième image à droite
    fused_picture.paste(image2, (image1.width, 0))

    # Ensure target directory exists
    fusion_dir = os.path.join(
        Paths.RESULTS_RESULTS,
        video_name,
        cropped_video_name,
        plot_name + "Fusion"
    )
    
    if not os.path.exists(fusion_dir):
        os.makedirs(fusion_dir)
        
    # Enregistrer l'image fusionnée
    output_path = os.path.join(fusion_dir, tps + "Fus.png")
    fused_picture.save(output_path)

def make_video_clip(filename, start, end, crop_width, crop_height, crop_x, crop_y, output_path):
    if not os.path.exists(filename):
        print(f"Error: Input file {filename} does not exist")
        return None
    
    cap = cv2.VideoCapture(filename)
    if not cap.isOpened():
        print(f"Error: Could not open video file {filename}")
        return None
    
    denominator = cap.get(cv2.CAP_PROP_FPS)
    if abs(denominator) < 1e-10:  # Avoid division by zero
        denominator = 1e-10 * (1 if denominator > 0 else -1)
    video_length = cap.get(cv2.CAP_PROP_FRAME_COUNT) / denominator
    if end > video_length:
        print(f"Warning: End time {end} exceeds video length {video_length}. Clamping.")
        end = video_length
    cap.release()

    if start < 0 or start >= end:
        print(f"Error: Invalid time range [{start}, {end}]")
        return None
    
    output_dir = os.path.dirname(Paths.DATA_BUFFER)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        subprocess.check_call([
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-ss", str(start),
            "-i", filename,
            "-t", str(end - start),
            "-map", "0:v",
            "-vf", f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}",
            "-vcodec", "libx264",
            "-crf", "18",
            "-preset", "ultrafast",
            output_path
        ])
    except Exception as e:
        print(f"Error creating video clip: {e}")

def extractImages(filename, folder_path, fps):
    original_fps = int(get_frame_rate(filename))
    if abs(fps) < 1e-10:  # Avoid division by zero
        fps = 1e-10 * (1 if fps > 0 else -1)
    jump = int(original_fps / fps)
    cap = cv2.VideoCapture(filename)
    success, image = cap.read()

    max_value, _ = dirNumber(folder_path)
    max_value += jump + 1
    while success:
        if max_value % jump == 0:
            output_path = os.path.join(folder_path, f"{max_value}.jpg")
            cv2.imwrite(output_path, image)
        success, image = cap.read()
        max_value += 1

def extraCropImages(filename, start, end, StopCal, frame, fps, used_model, pseudo, processing_chunk_counter):
    try:
        plt.clf()
    except Exception:
        pass

    # cut and crop video
    make_video_clip(filename, start, end, frame[3], frame[2], frame[1], frame[0], Paths.DATA_BUFFER)

    cap = cv2.VideoCapture(filename)
    if not StopCal:
        try:
            shutil.rmtree(Paths.DATA_IMS)
        except:
            pass
        os.makedirs(Paths.DATA_IMS, exist_ok=True)
        os.makedirs(Paths.DATA_IMS_STOCK, exist_ok=True)
        max_value, file_count = dirNumber(Paths.DATA_IMS_STOCK)
        if processing_chunk_counter == 0:
            file_count += 1
        img_folder_path = os.path.join(Paths.DATA_IMS_STOCK, f"ims{file_count}")
        os.makedirs(img_folder_path, exist_ok=True)
        max_value, _ = dirNumber(img_folder_path)
        extractImages(Paths.DATA_BUFFER, img_folder_path, fps)

        for filename in os.listdir(img_folder_path):
            debut = int(filename.replace(".jpg", ""))
            if debut >= max_value:
                img_path = os.path.join(
                    img_folder_path,
                    str(debut) + ".jpg"
                )
                try:
                    img = cv2.imread(img_path)
                    if img is not None:
                        cv2.imwrite(img_path, img)
                        shutil.copy(img_path, Paths.DATA_IMS)
                    else:
                        print(f"Error: Image {img_path} could not be read.")
                except Exception as e:
                    print(f"Error processing image {img_path}: {e}")
                    pass

        runserver(pseudo, used_model, processing_chunk_counter)
    cap.release()

    if used_model == PoseModel.MM_POSE:
        result_file_name = "mmpose-results"
    elif used_model == PoseModel.ALPHA_POSE:
        result_file_name = "alphapose-results"
    elif used_model == PoseModel.REP_NET:
        result_file_name = "repnet-results"
    if processing_chunk_counter != 0:
        result_file_name = result_file_name + str(processing_chunk_counter)
    result_file_name = result_file_name + ".json"
    
    path = os.path.join(Paths.RESULTS_RES, result_file_name)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    """
    if not os.path.exists(path):
        print(f"Warning: Result file {result_file_name} not found")
        return None
        
    """
    
    
    
    
    
    
    return result_file_name

################################################################################
############################# Code MOCAP AlphaPose #############################
################################################################################

def extractgraphs_ap_abd_add(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )
    
    print(filename)

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None

    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    angles = []
    listErr = [18]
    listToOk = [2, 5, 14, 15]
    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    for i in data:
        pose = AlphaPose(data, i)
        Nose = pose.get_nose()
        EyesD = pose.get_right_eyes()
        EyesG = pose.get_left_eyes()
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()

        denominator = EyesG[0] - EyesD[0]
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator >= 0 else -1)
        p_eyes = (EyesG[1] - EyesD[1]) / denominator
        denominator = SholG[0] - SholD[0]
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator >= 0 else -1)
        p_shou = (SholG[1] - SholD[1]) / denominator

        if abs(p_eyes) < 1e-10:  # Avoid division by zero
            p_eyes = 1e-10 * (1 if p_eyes >= 0 else -1)
        p_per1 = -1 / p_eyes

        o1 = Nose[1] - p_per1 * Nose[0]
        o2 = SholD[1] - p_shou * SholD[0]

        denominator = p_per1 - p_shou
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator >= 0 else -1)
        x = (o2 - o1) / denominator
        y = p_shou * x + o2

        if abs(p_shou) < 1e-10:  # Avoid division by zero
            p_shou = 1e-10 * (1 if p_shou >= 0 else -1)
        p_per2 = -1 / p_shou

        denominator = (1 - p_per2 * p_per1)
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator >= 0 else -1)
        angles.append(-np.degrees(np.arctan((p_per2 - p_per1) / denominator)))

    angles = filtreMoyenneur1D(angles, 7)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_ap_nodding(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            texte = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        texte = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        texte = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        texte = {}

    listErr = [18]
    listToOk = [0, 16, 17]

    for i in texte:
        for q in listToOk:
            if texte[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    distList = []
    for i in texte:
        pose = AlphaPose(texte, i)
        Nose = pose.get_nose()
        EarG = pose.get_left_ear()
        EarD = pose.get_right_ear()
        MEar = ((EarG[0] + EarD[0]) / 2, (EarG[1] + EarD[1]) / 2)
        distList.append(MEar[1] - Nose[1])

    distList = filtreMoyenneur1D(distList, 9)
    times = np.linspace(start, end, len(np.array(distList)))

    return listErr, [times.tolist(), distList]

def extractgraphs_ap_rotation(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [0, 2, 5, 14, 15, 16, 17]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    maxFact = 0
    change = True
    FactGtoD = {}
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_left_shoulder()
        SholG = pose.get_right_shoulder()
        MShol = pose.get_midshoulder()
        EarG = pose.get_right_ear()
        EarD = pose.get_left_ear()
        Nose = pose.get_nose()

        if change == True and maxFact < dist2points2D(EarG, Nose):
            maxFact = dist2points2D(EarG, Nose)
        if change == True and MShol[0] - 5 <= EarG[0] <= MShol[0] + 5:
            change = False
            maxFact = dist2points2D(EarG, Nose)

        FactGtoD[i] = MShol[0] - Nose[0]

    F = []
    maxFact = max(FactGtoD.values())
    if abs(maxFact) < 1e-10:  # Avoid division by zero
        maxFact = 1e-10 * (1 if maxFact >= 0 else -1)
    for i in FactGtoD:
        F.append(FactGtoD[i] * 90 / maxFact)

    RotDtoG = filtreMoyenneur1D(F, 7)
    times = np.linspace(start, end, len(np.array(F)))

    return listErr, [times.tolist(), RotDtoG]

def extractgraphs_ap_shrugging(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    processingChunkCounter_bis = processing_chunk_counter
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [0, 2, 5, 14, 15]
    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    gauche = []
    droite = []
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        gauche.append(SholG[1])
        droite.append(SholD[1])

    if processingChunkCounter_bis == 0:
        maxG = np.max(gauche)
        minG = np.min(gauche)
        maxD = np.max(droite)
        minD = np.min(droite)
        denominatorG = maxG - minG
        denominatorD = maxD - minD
        if abs(denominatorG) < 1e-10:  # Avoid division by zero
            denominatorG = 1e-10 * (1 if denominatorG >= 0 else -1)
        if abs(denominatorD) < 1e-10:  # Avoid division by zero
            denominatorD = 1e-10 * (1 if denominatorD >= 0 else -1)
        for i in range(len(data)):
            gauche[i] = 1 - (gauche[i] - minG) / denominatorG
            droite[i] = 1 - (droite[i] - minD) / denominatorD
        gauche = filtreMoyenneur1D(gauche, 7)
        droite = filtreMoyenneur1D(droite, 7)

    times = np.linspace(start, end, len(np.array(gauche)))

    return listErr, [times.tolist(), np.array(droite).tolist(), np.array(gauche).tolist()]

def extractgraphs_ap_abd_add_shoul(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [0, 2, 5]
    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    dist = []
    refDist = []
    distList = []
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        Nose = pose.get_nose()
        refDist.append(dist2points2D(SholD, Nose))
        dist.append(dist2points2D(SholD, SholG))

    maxRefDist = np.max(refDist)
    if abs(maxRefDist) < 1e-10:  # Avoid division by zero
        maxRefDist = 1e-10 * (1 if maxRefDist >= 0 else -1)
    maxDistRef = np.max(dist)
    j = 0
    for i in dist:
        if refDist[j] / maxRefDist > 0.60:
            distList.append(dist[j])
        else:
            distList.append(maxDistRef)
        j = j + 1

    if processing_chunk_counter == 0:
        maxDist = np.max(distList)
        minDist = np.min(distList)
        denominator = maxDist - minDist
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator >= 0 else -1)
        for i in range(len(distList)):
            distList[i] = (distList[i] - minDist) / denominator
        distList = filtreMoyenneur1D(distList, 17)

    times = np.linspace(start, end, len(np.array(distList)))

    return listErr, [times.tolist(), distList]

def extractgraphs_ap_arm_abduction(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [2, 3, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)
                print(data[i]["bodies"][0]["joints"][q * 3 + 2])

    anglesD = []
    anglesG = []
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        CouD = pose.get_right_elbow()
        CouG = pose.get_left_elbow()
        HipD = pose.get_right_hip()
        HipG = pose.get_left_hip()

        anglD = getAngle(SholD, CouD, HipD) - (90 - getAngle(SholD, SholG, HipD))
        anglG = getAngle(SholG, CouG, HipG) - (90 - getAngle(SholG, SholD, HipG))

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 5)
    anglesG = filtreMoyenneur1D(anglesG, 5)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [ times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_ap_arm_flexion(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [2, 3, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    fact = 0.6
    anglesD = []
    anglesG = []
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        CouD = pose.get_right_elbow()
        CouG = pose.get_left_elbow()

        shoulder_distance = dist2points2D(SholG, SholD)
        if abs(shoulder_distance) < 1e-10:  # Avoid division by zero
            shoulder_distance = 1e-10 * (1 if shoulder_distance >= 0 else -1)
        if (80 < angle_between_points(SholD, SholG, CouD) < 120
        or 220 < angle_between_points(SholD, SholG, CouD) < 260
        or dist2points2D(CouD, SholD) / shoulder_distance < fact):
            if CouD[1] > SholD[1]:
                anglD = 90 * (1 - dist2points2D(CouD, SholD) / shoulder_distance)
            else:
                anglD = 90 * (1 + dist2points2D(CouD, SholD) / shoulder_distance)
        else:
            anglD = 0

        if (80 < angle_between_points(SholG, CouG, SholD) < 120
        or 220 < angle_between_points(SholG, CouG, SholD) < 260
        or dist2points2D(SholG, CouG) / shoulder_distance < fact):
            if CouG[1] > SholG[1]:
                anglG = 90 * (1 - dist2points2D(SholG, CouG) / shoulder_distance)
            else:
                anglG = 90 * (1 + dist2points2D(SholG, CouG) / shoulder_distance)
        else:
            anglG = 0

        anglesD.append(max(anglD, 0))
        anglesG.append(max(anglG, 0))

    anglesD = filtreMoyenneur1D(anglesD, 7)
    anglesG = filtreMoyenneur1D(anglesG, 7)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [ times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_ap_forearm_flexion(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [2, 3, 4, 5, 6, 7]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    anglesD = []
    anglesG = []
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        CouD = pose.get_right_elbow()
        CouG = pose.get_left_elbow()
        PoigD = pose.get_right_wrist()
        PoigG = pose.get_left_wrist()

        anglG = getAngle(CouG, PoigG, SholG)
        anglD = getAngle(CouD, SholD, PoigD)

        # Quand l'avant-bras fait une ligne droite en passant par l'avant du corps et non en faisant un tour sur le côté
        if not (30 < anglG < 300) or (
            dist2points2D(CouG, PoigG) < dist2points2D(CouG, SholG) / 2
        ):
            anglG += 180
        if not (30 < anglD < 300) or (
            dist2points2D(CouD, PoigD) < dist2points2D(CouD, SholD) / 2
        ):
            anglD += 180

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 7)
    anglesG = filtreMoyenneur1D(anglesG, 7)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [ times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_ap_buste_flexion(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    processingChunkCounter_bis = processing_chunk_counter
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [2, 5, 8, 11]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    distNormT = []
    for i in data:
        pose = AlphaPose(data, i)

        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        HipD = pose.get_right_hip()
        HipG = pose.get_left_hip()

        angle = getAngleVecNega(vecteurCord(SholD, SholG), vecteurCord(HipD, HipG))
        if abs(angle) < 15:
            distNormT.append(dist2points2D(pose.get_midshoulder(), pose.get_midhip()))

    if processingChunkCounter_bis == 0:
        minDist = np.min(distNormT)
        maxDist = np.max(distNormT)
        denominator = maxDist - minDist
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator >= 0 else -1)
        for i in range(len(distNormT)):
            distNormT[i] = (distNormT[i] - minDist) / denominator
        distNorm = filtreMoyenneur1D(distNormT, 5)

    times = np.linspace(start, end, len(np.array(distNorm)))

    return listErr, [times.tolist(), np.array(distNorm).tolist()]

def extractgraphs_ap_buste_abd_add(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [0, 2, 5, 8, 11]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    angles = []
    for i in data:
        pose = AlphaPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_right_hip())
        points[i].append(pose.get_left_hip())
        points[i].append(pose.get_nose())

        angles.append(
            getAngleVecNega(
                vecteurCord(points[i][0], points[i][1]),
                vecteurCord(points[i][2], points[i][3]),
            )
        )

    angles = filtreMoyenneur1D(angles, 11)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_ap_buste_rotation(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        # Return empty data with default structure
        return [18], [np.linspace(start, end, 2).tolist(), [0, 0]]
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        # Return empty data with default structure
        return [18], [np.linspace(start, end, 2).tolist(), [0, 0]]
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        # Return empty data with default structure
        return [18], [np.linspace(start, end, 2).tolist(), [0, 0]]

    listErr = [18]
    listToOk = [0, 2, 5, 8, 11]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    angles = []
    for i in data:
        pose = AlphaPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        HipD = pose.get_right_hip()
        HipG = pose.get_left_hip()
        Nose = pose.get_nose()

        denominator = dist2points2D(HipD, HipG)
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        fact = dist2points2D(SholD, SholG) / denominator  # Pour savoir s'il est de profil ou de face

        maxFact = 1.7  # dist2points2D(HipD,HipG)/dist2points2D(SholD,SholG)

        if abs(HipG[0] - Nose[0]) > abs(Nose[0] - HipD[0]):
            angles.append(90 * (maxFact - fact) + 10)
        elif -10 < abs(HipG[0] - Nose[0]) - abs(Nose[0] - HipD[0]) < 10:
            angles.append(0)
        else:
            angles.append(90 * (fact - maxFact) + 10)

    angles = filtreMoyenneur1D(angles, 11)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]
    

def extractgraphs_ap_lat_nod(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [0, 16, 17]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    angles = []
    for i in data:
        pose = AlphaPose(data, i)
        Nose = pose.get_nose()
        EarG = pose.get_left_ear()
        EarD = pose.get_right_ear()
        MEar = ((EarG[0] + EarD[0]) / 2, (EarG[1] + EarD[1]) / 2)
        if MEar[1] - 10 <= Nose[1] <= MEar[1] + 10:
            angles.append(0)
        else:
            angles.append(MEar[1] - Nose[1])

    angles = filtreMoyenneur1D(angles, 5)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_ap_arm_flexion_lat(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Error: Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [18]
    listToOk = [0, 2, 3, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    anglesD = []
    anglesG = []
    for i in data:
        pose = AlphaPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_right_elbow())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_left_elbow())
        points[i].append((0, 0))
        points[i].append((0, 1))
        points[i].append(pose.get_nose())

        if dist2points2D(points[i][0], points[i][2]) < dist2points2D(
            points[i][0], points[i][6]
        ):
            if (points[i][0][0] + points[i][2][0]) / 2 > points[i][6][0]:
                anglD = -getAngleVecNega(
                    vecteurCord(points[i][0], points[i][1]),
                    vecteurCord(points[i][4], points[i][5]),
                )
                anglG = -getAngleVecNega(
                    vecteurCord(points[i][2], points[i][3]),
                    vecteurCord(points[i][4], points[i][5]),
                )
            else:
                anglD = getAngleVecNega(
                    vecteurCord(points[i][0], points[i][1]),
                    vecteurCord(points[i][4], points[i][5]),
                )
                anglG = getAngleVecNega(
                    vecteurCord(points[i][2], points[i][3]),
                    vecteurCord(points[i][4], points[i][5]),
                )
        else:
            anglD = 0
            anglG = 0

        if points[i][0][1] > points[i][1][1] and anglD < 0:
            anglD = 360 + anglD
        if points[i][2][1] > points[i][3][1] and anglG < 0:
            anglG = 360 + anglG

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 7)
    anglesG = filtreMoyenneur1D(anglesG, 7)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_ap_nodding_lat(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.ALPHA_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by AlphaPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            texte = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        texte = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        texte = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        texte = {}

    listErr = [17]
    listToOk = [0, 3, 4]

    for i in texte:
        for q in listToOk:
            if texte[i]["bodies"][0]["joints"][q * 3 + 2] < 0.2 and q not in listErr:
                listErr.append(q)

    distList = []
    for i in texte:
        pose = AlphaPose(texte, i)
        Nose = pose.get_nose()
        EarG = pose.get_left_ear()
        EarD = pose.get_right_ear()
        MEar = ((EarG[0] + EarD[0]) / 2, (EarG[1] + EarD[1]) / 2)
        MHip = pose.get_midhip()
        MSho = pose.get_midshoulder()
        distList.append(getAngleVec(vecteurCord(MHip, MSho), vecteurCord(Nose, MEar)))

    distList = filtreMoyenneur1D(distList, 9)
    times = np.linspace(start, end, len(np.array(distList)))

    return listErr, [times.tolist(), distList]

################################################################################
############################### Code MOCAP MMPose ##############################
################################################################################

def extractgraphs_mp_abd_add(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    angles = []
    listErr = [17]
    listToOk = [0, 1, 2, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    for i in data:
        pose = MMPose(data, i)
        Nose = pose.get_nose()
        EyesD = pose.get_right_eyes()
        EyesG = pose.get_left_eyes()
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()

        denominator = EyesG[0] - EyesD[0]
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        p_eyes = (EyesG[1] - EyesD[1]) / denominator
        denominator = SholG[0] - SholD[0]
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        p_shou = (SholG[1] - SholD[1]) / denominator

        if abs(p_eyes) < 1e-10:  # Avoid division by zero
            p_eyes = 1e-10 * (1 if p_eyes > 0 else -1)
        p_per1 = -1 / p_eyes

        o1 = Nose[1] - p_per1 * Nose[0]
        o2 = SholD[1] - p_shou * SholD[0]

        denominator = p_per1 - p_shou
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        x = (o2 - o1) / denominator
        y = p_shou * x + o2

        if abs(p_shou) < 1e-10:  # Avoid division by zero
            p_shou = 1e-10 * (1 if p_shou > 0 else -1)
        p_per2 = -1 / p_shou

        denominator = 1 - p_per2 * p_per1
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        angles.append(-np.degrees(np.arctan((p_per2 - p_per1) / denominator)))

    angles = filtreMoyenneur1D(angles, 11)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_mp_nodding(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            texte = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        texte = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        texte = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        texte = {}

    listErr = [17]
    listToOk = [0, 3, 4]

    for i in texte:
        for q in listToOk:
            if texte[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    distList = []
    for i in texte:
        pose = MMPose(texte, i)
        Nose = pose.get_nose()
        EarG = pose.get_left_ear()
        EarD = pose.get_right_ear()
        MEar = ((EarG[0] + EarD[0]) / 2, (EarG[1] + EarD[1]) / 2)
        distList.append(MEar[1] - Nose[1])

    distList = filtreMoyenneur1D(distList, 9)
    times = np.linspace(start, end, len(np.array(distList)))

    return listErr, [times.tolist(), distList]

def extractgraphs_mp_rotation(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    FactGtoD = {}
    listErr = [17]
    listToOk = [0, 1, 2, 3, 4, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    max = 0
    change = True
    for i in data:
        pose = MMPose(data, i)
        SholD = pose.get_left_shoulder()
        SholG = pose.get_right_shoulder()
        MShol = pose.get_midshoulder()
        EyesD = pose.get_left_eyes()
        EyesG = pose.get_right_eyes()
        EarD = pose.get_left_ear()
        EarG = pose.get_right_ear()
        Nose = pose.get_nose()

        denominator = SholD[0] - SholG[0]
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        m = (SholD[1] - SholG[1]) / denominator
        b = MShol[1] - m * MShol[0]

        if 0 <= m <= 0.0001:
            m2 = -10000
        elif 0 > m >= -0.0001:
            m2 = 10000
        else:
            m2 = -1 / m

        b0 = Nose[1] - m2 * Nose[0]
        a1 = -m2
        c1 = b0
        a2 = -m
        c2 = b
        determinant = a1 - a2
        if abs(determinant) < 1e-10:  # Avoid division by zero
            determinant = 1e-10 * (1 if determinant > 0 else -1)
        xh = (c1 - c2) / determinant
        yh = (a1 * c2 - a2 * c1) / determinant

        if change == True and max < dist2points2D(EarG, Nose):
            max = dist2points2D(EarG, Nose)
        if change == True and MShol[0] - 5 <= EarG[0] <= MShol[0] + 5:
            change = False
            max = dist2points2D(EarG, Nose)

        erreur = 0.8
        if dist2point2D(EarG[0], EarG[1], Nose[0], Nose[1]) != 0:
            denominator = dist2point2D(EarG[0], EarG[1], Nose[0], Nose[1])
            if abs(denominator) < 1e-10:  # Avoid division by zero
                denominator = 1e-10 * (1 if denominator > 0 else -1)
            factEarNoze = dist2point2D(EarD[0], EarD[1], Nose[0], Nose[1]) / denominator
        else:
            factEarNoze = 1000
        if erreur < factEarNoze < 1 / erreur and (EyesD[0] < Nose[0] < EyesG[0]):
            FactGtoD[i] = 0
        else:
            denominator = dist2points2D(MShol, SholD)
            if abs(denominator) < 1e-10:  # Avoid division by zero
                denominator = 1e-10 * (1 if denominator > 0 else -1)
            if MShol[0] > xh:
                FactGtoD[i] = (90 * dist2point2D(MShol[0], MShol[1], xh, yh) / denominator)
            else:
                FactGtoD[i] = (-90 * dist2point2D(MShol[0], MShol[1], xh, yh) / denominator)

    F = []
    for i in FactGtoD:
        F.append(FactGtoD[i])

    RotDtoG = filtreMoyenneur1D(F, 7)
    times = np.linspace(start, end, len(np.array(F)))

    return listErr, [times.tolist(), RotDtoG.tolist()]

def extractgraphs_mp_shrugging(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    processingChunkCounter_bis = processing_chunk_counter
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [0, 1, 2, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    gauche = []
    droite = []
    for i in data:
        pose = MMPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        gauche.append(SholG[1])
        droite.append(SholD[1])

    if processingChunkCounter_bis == 0:
        maxG = np.max(gauche)
        minG = np.min(gauche)
        maxD = np.max(droite)
        minD = np.min(droite)
        denominatorG = maxG - minG
        denominatorD = maxD - minD
        if abs(denominatorG) < 1e-10:  # Avoid division by zero
            denominatorG = 1e-10 * (1 if denominatorG > 0 else -1)
        if abs(denominatorD) < 1e-10:  # Avoid division by zero
            denominatorD = 1e-10 * (1 if denominatorD > 0 else -1)
        for i in range(len(data)):
            gauche[i] = 1 - (gauche[i] - minG) / denominatorG
            droite[i] = 1 - (droite[i] - minD) / denominatorD
        gauche = filtreMoyenneur1D(gauche, 7)
        droite = filtreMoyenneur1D(droite, 7)

    times = np.linspace(start, end, len(np.array(gauche)))

    return listErr, [times.tolist(), np.array(droite).tolist(), np.array(gauche).tolist()]

def extractgraphs_mp_abd_add_shoul(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [0, 5, 6]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    dist = []
    refDist = []
    distList = []
    for i in data:
        pose = MMPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        Nose = pose.get_nose()
        refDist.append(dist2points2D(SholD, Nose))
        dist.append(dist2points2D(SholD, SholG))

    maxRefDist = np.max(refDist)
    if abs(maxRefDist) < 1e-10:  # Avoid division by zero
        maxRefDist = 1e-10 * (1 if maxRefDist > 0 else -1)
    maxDistRef = np.max(dist)
    for j, current_dist in enumerate(dist):
        if refDist[j] / maxRefDist > 0.60:
            distList.append(current_dist)
        else:
            distList.append(maxDistRef)

    if processing_chunk_counter == 0:
        maxDist = np.max(distList)
        minDist = np.min(distList)
        denominator = maxDist - minDist
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        for i in range(len(distList)):
            distList[i] = (distList[i] - minDist) / denominator
        distList = filtreMoyenneur1D(distList, 17)

    times = np.linspace(start, end, len(np.array(distList)))

    return listErr, [times.tolist(), distList]

def extractgraphs_mp_arm_abduction(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [5, 6, 7, 8]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    anglesD = []
    anglesG = []
    for i in data:
        pose = MMPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_right_elbow())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_left_elbow())

        anglD = angle_between_points(points[i][0], points[i][2], points[i][1])
        anglG = angle_between_points(points[i][2], points[i][3], points[i][0])

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 5)
    anglesG = filtreMoyenneur1D(anglesG, 5)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_mp_arm_flexion(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [5, 6, 7, 8]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    anglesD = []
    anglesG = []
    for i in data:
        pose = MMPose(data, i)
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        CouD = pose.get_right_elbow()
        CouG = pose.get_left_elbow()
        HipD = pose.get_right_hip()
        HipG = pose.get_left_hip()

        anglD = getAngle(SholD, CouD, HipD) - (90 - getAngle(SholD, SholG, HipD))
        anglG = getAngle(SholG, CouG, HipG) - (90 - getAngle(SholG, SholD, HipG))

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 7)
    anglesG = filtreMoyenneur1D(anglesG, 7)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_mp_forearm_flexion(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [5, 6, 7, 8, 9, 10]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    anglesD = []
    anglesG = []
    for i in data:
        pose = MMPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_right_elbow())
        points[i].append(pose.get_right_wrist())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_left_elbow())
        points[i].append(pose.get_left_wrist())

        anglD = getAngleVec(
            vecteurCord(points[i][1], points[i][0]),
            vecteurCord(points[i][1], points[i][2]),
        )
        anglG = getAngleVec(
            vecteurCord(points[i][4], points[i][3]),
            vecteurCord(points[i][4], points[i][5]),
        )

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 7)
    anglesG = filtreMoyenneur1D(anglesG, 7)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_mp_buste_flexion(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    processingChunkCounter_bis = processing_chunk_counter
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [5, 6, 11, 12]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    distNormT = []
    for i in data:
        pose = MMPose(data, i)
        points[i] = []
        SholD = pose.get_right_shoulder()
        SholG = pose.get_left_shoulder()
        HipD = pose.get_right_hip()
        HipG = pose.get_left_hip()
        MHip = pose.get_midhip()
        MShol = pose.get_midshoulder()

        distNormT.append(
            np.mean(
                [
                    dist2points2D(MShol, MHip),
                    dist2points2D(SholD, HipD),
                    dist2points2D(SholG, HipG),
                ]
            )
        )

    if processingChunkCounter_bis == 0:
        minDist = np.min(distNormT)
        maxDist = np.max(distNormT)
        denominator = maxDist - minDist
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        for i in range(len(distNormT)):
            distNormT[i] = (distNormT[i] - minDist) / denominator
        distNorm = filtreMoyenneur1D(distNormT, 5)

    times = np.linspace(start, end, len(np.array(distNorm)))

    return listErr, [times.tolist(), np.array(distNorm).tolist()]

def extractgraphs_mp_buste_abd_add(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [0, 5, 6, 11, 12]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    angles = []
    points = {}
    for i in data:
        pose = MMPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_right_hip())
        points[i].append(pose.get_left_hip())
        points[i].append(pose.get_nose())

        angles.append(
            getAngleVecNega(
                vecteurCord(points[i][0], points[i][1]),
                vecteurCord(points[i][2], points[i][3]),
            )
        )

    angles = filtreMoyenneur1D(angles, 11)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_mp_buste_rotation(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [0, 5, 6, 11, 12]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    angles = []
    for i in data:
        pose = MMPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_right_hip())
        points[i].append(pose.get_left_hip())
        points[i].append(pose.get_nose())

        angle = getAngleVecNega(vecteurCord(points[i][0], points[i][1]), vecteurCord(points[i][2], points[i][3])) # TODO: check if this is really unused
        denominator = dist2points2D(points[i][2], points[i][3])
        if abs(denominator) < 1e-10:  # Avoid division by zero
            denominator = 1e-10 * (1 if denominator > 0 else -1)
        fact = dist2points2D(points[i][0], points[i][1]) / denominator

        multi = 40
        maxFact = 1.7
        if fact < 1:
            if abs(points[i][3][0] - points[i][4][0]) > abs(points[i][4][0] - points[i][2][0]):
                angles.append(multi * (maxFact - fact))
            elif abs(points[i][3][0] - points[i][4][0]) == abs(points[i][4][0] - points[i][2][0]):
                angles.append(0)
            else:
                angles.append(multi * (fact - maxFact))
        else:
            angles.append(0)

    angles = filtreMoyenneur1D(angles, 11)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_mp_lat_nod(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [0, 3, 4]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    angles = []
    for i in data:
        pose = MMPose(data, i)
        Nose = pose.get_nose()
        EarG = pose.get_left_ear()
        EarD = pose.get_right_ear()
        MEar = ((EarG[0] + EarD[0]) / 2, (EarG[1] + EarD[1]) / 2)
        if MEar[1] - 10 <= Nose[1] <= MEar[1] + 10:
            angles.append(0)
        else:
            angles.append(MEar[1] - Nose[1])

    angles = filtreMoyenneur1D(angles, 9)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), angles]

def extractgraphs_mp_arm_flexion_lat(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        data = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        data = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        data = {}

    listErr = [17]
    listToOk = [0, 5, 6, 7, 8]

    for i in data:
        for q in listToOk:
            if data[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    points = {}
    anglesD = []
    anglesG = []
    for i in data:
        pose = MMPose(data, i)
        points[i] = []
        points[i].append(pose.get_right_shoulder())
        points[i].append(pose.get_right_elbow())
        points[i].append(pose.get_left_shoulder())
        points[i].append(pose.get_left_elbow())
        points[i].append((0, 0))
        points[i].append((0, 1))
        points[i].append(pose.get_nose())

        if dist2points2D(points[i][0], points[i][2]) < dist2points2D(
            points[i][0], points[i][6]
        ):
            if (points[i][0][0] + points[i][2][0]) / 2 > points[i][6][0]:
                anglD = -getAngleVecNega(
                    vecteurCord(points[i][0], points[i][1]),
                    vecteurCord(points[i][4], points[i][5]),
                )
                anglG = -getAngleVecNega(
                    vecteurCord(points[i][2], points[i][3]),
                    vecteurCord(points[i][4], points[i][5]),
                )
            else:
                anglD = getAngleVecNega(
                    vecteurCord(points[i][0], points[i][1]),
                    vecteurCord(points[i][4], points[i][5]),
                )
                anglG = getAngleVecNega(
                    vecteurCord(points[i][2], points[i][3]),
                    vecteurCord(points[i][4], points[i][5]),
                )
        else:
            anglD = 0
            anglG = 0

        if points[i][0][1] > points[i][1][1] and anglD < 0:
            anglD = 360 + anglD
        if points[i][2][1] > points[i][3][1] and anglG < 0:
            anglG = 360 + anglG

        anglesD.append(anglD)
        anglesG.append(anglG)

    anglesD = filtreMoyenneur1D(anglesD, 7)
    anglesG = filtreMoyenneur1D(anglesG, 7)
    times = np.linspace(start, end, len(np.array(anglesD)))

    return listErr, [times.tolist(), np.array(anglesD).tolist(), np.array(anglesG).tolist()]

def extractgraphs_mp_nodding_lat(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.MM_POSE, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by MMPose")
        return None, None
    
    try:
        result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
        with open(result_file_path, "r") as f:
            texte = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {result_file_path}")
        texte = {}
    except json.JSONDecodeError:
        print(f"Error: Could not parse JSON from {result_file_path}")
        texte = {}
    except Exception as e:
        print(f"Unexpected error reading {result_file_path}: {e}")
        texte = {}

    listErr = [17]
    listToOk = [0, 3, 4]

    for i in texte:
        for q in listToOk:
            if texte[i][0]["keypoint_scores"][q] < 0.2 and q not in listErr:
                listErr.append(q)

    distList = []
    for i in texte:
        pose = MMPose(texte, i)
        Nose = pose.get_nose()
        EarG = pose.get_left_ear()
        EarD = pose.get_right_ear()
        MEar = ((EarG[0] + EarD[0]) / 2, (EarG[1] + EarD[1]) / 2)
        MHip = pose.get_midhip()
        MSho = pose.get_midshoulder()
        distList.append(getAngleVec(vecteurCord(MHip, MSho), vecteurCord(Nose, MEar)))

    distList = filtreMoyenneur1D(distList, 9)
    times = np.linspace(start, end, len(np.array(distList)))

    return listErr, [times.tolist(), distList]

################################################################################
############################### Code MOCAP RepNet ##############################
################################################################################

def extract_repnet_info(result_file_name):
    print(result_file_name)
    result_file_path = os.path.join(Paths.RESULTS_RES, result_file_name)
    with open(result_file_path, "r") as f:
        data = json.load(f)

    abdadd = []
    nodding = []
    rot = []
    for frame in data:
        rot.append(data[frame]["keypoints_scores"][0])
        nodding.append(data[frame]["keypoints_scores"][1])
        abdadd.append(data[frame]["keypoints_scores"][2])

    return nodding, abdadd, rot

def extractgraphs_rp_abd_add(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.REP_NET, pseudo, processing_chunk_counter
    )

    if result_file_name is None:
        print("Error: No results file generated by 6DRepNet")
        return None, None

    listErr = []
    _, angle, _ = extract_repnet_info(result_file_name)
    angles = []
    for i in range(len(angle)):
        angles.append(-angle[i])
    angles = filtreMoyenneur1D(angles, 9)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_rp_nodding(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.REP_NET, pseudo, processing_chunk_counter
    )
    
    if result_file_name is None:
        print("Error: No results file generated by 6DRepNet")
        return None, None

    listErr = []
    angles, _, _ = extract_repnet_info(result_file_name)
    angles = filtreMoyenneur1D(angles, 5)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]

def extractgraphs_rp_rotation(filename, start, end, fps, frame, StopCal, pseudo, processing_chunk_counter=0):
    end_bis = end
    result_file_name = extraCropImages(
        filename, start, end_bis, StopCal, frame, fps, PoseModel.REP_NET, pseudo, processing_chunk_counter
    )
    
    if result_file_name is None:
        print("Error: No results file generated by 6DRepNet")
        return None, None

    listErr = []
    _, _, angles = extract_repnet_info(result_file_name)
    angles = filtreMoyenneur1D(angles, 11)
    times = np.linspace(start, end, len(np.array(angles)))

    return listErr, [times.tolist(), np.array(angles).tolist()]
