# Standard library imports
import datetime
import os
import shutil
import sys
from threading import Thread

# PyQt5 imports
from PyQt5.QtCore import QDir, Qt, QUrl, QTimer, QEvent
from PyQt5.QtGui import QCursor, QIcon, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QAction, QApplication, QButtonGroup, QCheckBox,
    QFileDialog, QGridLayout, QHBoxLayout, QDialog,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSlider, QStyle, QSpacerItem,
    QVBoxLayout, QWidget, QSizePolicy, QProgressBar
)

# Third-party imports
import cv2
import ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Set matplotlib backend
import matplotlib as mpl
mpl.use("Agg")

# Local imports
from account_manager import AccountManager
from RubberBandWidget import RubberBandWidget
from help_dialog import show_help_dialog
from constants import PoseModel, VideoState, VideoMode, Paths
import constants
import mocap1 as mc

def add_date_time_to_path(filename):
    now = datetime.datetime.now()
    date_time_suffix = now.strftime("_%d%m%Y_h%H%M%S")
    return filename + date_time_suffix

# Custom event classes for analysis completion and error
class AnalysisCompleteEvent(QEvent):
    def __init__(self):
        super().__init__(QEvent.Type(QEvent.User + 1))

class AnalysisErrorEvent(QEvent):
    def __init__(self, error_message="An error occurred during analysis.", exception=None):
        super().__init__(QEvent.Type(QEvent.User + 2))
        self.error_message = error_message
        self.exception = exception

class ModelErrorEvent(QEvent):
    def __init__(self, model_type="pose estimation"):
        super().__init__(QEvent.Type(QEvent.User + 3))
        self.model_type = model_type

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_state = VideoState.PLAYING
        self.cursor = QCursor(QPixmap(os.path.join(Paths.ASSETS_GUI, "mouse.png")))
        self.account_manager = AccountManager(Paths.ASSETS_GUI, Paths.ASSETS_RSA_KEY)
        self.account_manager.account_changed.connect(self.update_username)
        self.username = ""
        self.fps = 1
        self.filename = ""
        self.lastPathToDelete = ["", ""]
        self.last_path_ims_to_delete = ""
        self.previous_processed_data = [0.0, 0.0, ""]
        self.analysis_name = ""

        # MainWindow settings
        self.setWindowIcon(QIcon(os.path.join(Paths.ASSETS_GUI, "logo.png")))
        self.setWindowTitle("Body-to-Text Motion Analyzer 4.2.0")

        # MenuBar File Tab actions
        open_action_icon = QIcon(os.path.join(Paths.ASSETS_GUI, "open.png"))
        self.open_file_action = QAction(open_action_icon, "&Open", self)
        self.open_file_action.setShortcut("Ctrl+O")
        self.open_file_action.setStatusTip("Open File")
        self.open_file_action.triggered.connect(self.handle_open_file_action)

        exit_action_icon = QIcon(os.path.join(Paths.ASSETS_GUI, "exit.png"))
        self.exit_action = QAction(exit_action_icon, "&Exit", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.setStatusTip("Exit application")
        self.exit_action.triggered.connect(self.handle_exit_action)

        save_plots_action = QIcon(os.path.join(Paths.ASSETS_GUI, "savePlot.png"))
        self.save_plots_action = QAction(save_plots_action, "&Save Plots as", self)
        self.save_plots_action.setShortcut("Ctrl+W")
        self.save_plots_action.setStatusTip("Save Plots")
        self.save_plots_action.triggered.connect(self.handle_save_plots_action)
        self.save_plots_action.setEnabled(False)

        save_excel_action = QIcon(os.path.join(Paths.ASSETS_GUI, "saveEx.png"))
        self.save_excel_action = QAction(save_excel_action, "&Save Excel as", self)
        self.save_excel_action.setShortcut("Ctrl+T")
        self.save_excel_action.setStatusTip("Save Excel")
        self.save_excel_action.triggered.connect(self.handle_save_excel_action)
        self.save_excel_action.setEnabled(False)

        save_slices_action = QIcon(os.path.join(Paths.ASSETS_GUI, "saveImage.png"))
        self.save_slices_action = QAction(save_slices_action, "&Save Slices as", self)
        self.save_slices_action.setShortcut("Ctrl+R")
        self.save_slices_action.setStatusTip("Save Slices")
        self.save_slices_action.triggered.connect(self.handle_save_slices_action)
        self.save_slices_action.setEnabled(False)

        # MenuBar File Tab
        file_menu = QMenu("&File", self)
        file_menu.addAction(self.open_file_action)
        file_menu.addAction(self.exit_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_plots_action)
        file_menu.addAction(self.save_excel_action)
        file_menu.addAction(self.save_slices_action)

        # MenuBar Option Tab
        option_menu = QMenu("&Option", self)
        option_menu.addAction(self.account_manager.create_account_action(self))

        # MenuBar Help Tab
        help_menu = QMenu("&Help", self)
        help_action_icon = QIcon(os.path.join(Paths.ASSETS_GUI, "help.png"))
        self.help_action = QAction(help_action_icon, "&Help", self)
        self.help_action.triggered.connect(lambda:show_help_dialog(self, Paths.ASSETS_GUI))
        help_menu.addAction(self.help_action)

        # MenuBar
        self.menu_bar = self.menuBar()
        self.menu_bar.addMenu(file_menu)
        self.menu_bar.addMenu(option_menu)
        self.menu_bar.addMenu(help_menu)

        # Landing page
        self.landing_image_label = QLabel()
        self.landing_image_label.setAlignment(Qt.AlignCenter)
        self.landing_image_label.setPixmap(QPixmap(os.path.join(Paths.ASSETS_GUI, "background.png")))
        self.landing_open_button = QPushButton("Open File")
        self.landing_open_button.clicked.connect(self.handle_open_file_action)
        landing_layout = QVBoxLayout()
        landing_layout.addWidget(self.landing_image_label)
        landing_layout.addWidget(self.landing_open_button)

        # Video player
        self.rubber_band_widget = RubberBandWidget()
        self.video_widget = QVideoWidget()
        self.video_play_button = QPushButton()
        self.video_play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.video_play_button.clicked.connect(lambda: self.video_change_playing_state(VideoState.PLAYING if self.video_state == VideoState.PAUSED else VideoState.PAUSED))
        self.video_media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_media_player.setVideoOutput(self.video_widget)
        self.video_media_player.positionChanged.connect(self.handle_position_changed)
        self.video_media_player.durationChanged.connect(self.handle_duration_changed)
        self.video_timestamp_label = QLabel(str(self.video_media_player.position()))
        self.video_timestamp_label.setAlignment(Qt.AlignCenter)
        self.video_timestamp_label.setMinimumWidth(60)  # Important to avoid moving the slider when the label is updated and making navigation difficult
        self.video_seekbar_slider = QSlider(Qt.Horizontal)
        self.video_seekbar_slider.setRange(0, 0)
        self.video_seekbar_slider.setSingleStep(1)
        self.video_seekbar_slider.sliderMoved.connect(self.handle_video_seekbar)
        self.video_select_area_button = QPushButton("Select Area")
        self.video_select_area_button.clicked.connect(self.get_crop_coords)
        self.video_change_mode_button = QPushButton("Change to full video")
        self.video_change_mode_button.clicked.connect(lambda: self.video_change_mode(VideoMode.CROPPED if self.is_long_video_mode else VideoMode.FULL))
        self.generated_plots_label = QLabel(self)
        # The label containing the generated plots, it scales but doesn't keep the aspect ratio... i couldn't find a way to do it
        self.generated_plots_label.setScaledContents(True)
        self.generated_plots_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.generated_plots_label.setMinimumSize(10, 10)

        # Video layout
        video_play_button_seekbar_layout = QHBoxLayout()
        video_play_button_seekbar_layout.addWidget(self.video_play_button)
        video_play_button_seekbar_layout.addWidget(self.video_timestamp_label)
        video_play_button_seekbar_layout.addWidget(self.video_seekbar_slider)
        video_special_options_layout = QHBoxLayout()
        video_special_options_layout.addWidget(self.video_select_area_button)
        video_special_options_layout.addWidget(self.video_change_mode_button)
        video_layout = QVBoxLayout()
        video_layout.addWidget(self.rubber_band_widget)
        video_layout.addWidget(self.video_widget)
        video_layout.addLayout(video_play_button_seekbar_layout)
        video_layout.addLayout(video_special_options_layout)
        video_plots_layout = QHBoxLayout()
        video_plots_layout.addLayout(video_layout, 1)
        video_plots_layout.addWidget(self.generated_plots_label, 2)

        # Model choice
        self.model_choice_label = QLabel("Model")
        self.model_choice_label.setAlignment(Qt.AlignCenter)
        self.alphapose_checkbox = QCheckBox("AlphaPose", self)
        self.mmpose_checkbox = QCheckBox("MMPose", self)
        self.repnet_checkbox = QCheckBox("6DRepNet", self)
        self.alphapose_checkbox.setChecked(True)
        model_choice_button_group = QButtonGroup(self)
        model_choice_button_group.addButton(self.alphapose_checkbox)
        model_choice_button_group.addButton(self.mmpose_checkbox)
        model_choice_button_group.addButton(self.repnet_checkbox)
        model_choice_button_group.setExclusive(True)
        model_choice_button_group.idClicked.connect(self.handle_model_checkboxes)
        model_choice_layout = QVBoxLayout()
        model_choice_layout.addWidget(self.alphapose_checkbox)
        model_choice_layout.addWidget(self.mmpose_checkbox)
        model_choice_layout.addWidget(self.repnet_checkbox)

        # Options
        self.option_label = QLabel("Options")
        self.option_label.setAlignment(Qt.AlignCenter)
        self.option_delete_last_checkbox = QCheckBox("Delete Last Slices")
        self.option_delete_last_checkbox.clicked.connect(self.handle_delete_last)
        self.option_delete_last_checkbox.setChecked(False)
        self.option_show_limit_checkbox = QCheckBox("Include Limit of Data")
        self.option_show_limit_checkbox.setChecked(True)
        options_layout = QVBoxLayout()
        options_layout.addWidget(self.option_delete_last_checkbox)
        options_layout.addWidget(self.option_show_limit_checkbox)

        # Body part selection
        self.body_part_label = QLabel("Limb to study")
        self.body_part_label.setAlignment(Qt.AlignCenter)
        self.body_part_selection_button_group = QButtonGroup(self)
        self.body_part_selection_button_group.setExclusive(True)
        self.head_checkbox = QCheckBox("Head")
        self.shoulder_checkbox = QCheckBox("Shoulder")
        self.torso_checkbox = QCheckBox("Torso")
        self.arm_checkbox = QCheckBox("Arm")
        self.forearm_checkbox = QCheckBox("Fore Arm")
        self.head_checkbox.setChecked(True)
        self.body_part_selection_button_group.addButton(self.head_checkbox)
        self.body_part_selection_button_group.addButton(self.shoulder_checkbox)
        self.body_part_selection_button_group.addButton(self.torso_checkbox)
        self.body_part_selection_button_group.addButton(self.arm_checkbox)
        self.body_part_selection_button_group.addButton(self.forearm_checkbox)
        self.body_part_selection_button_group.idClicked.connect(self.handle_body_part_checkboxes)
        body_part_selection_layout = QVBoxLayout()
        body_part_selection_layout.addWidget(self.head_checkbox)
        body_part_selection_layout.addWidget(self.shoulder_checkbox)
        body_part_selection_layout.addWidget(self.torso_checkbox)
        body_part_selection_layout.addWidget(self.arm_checkbox)
        body_part_selection_layout.addWidget(self.forearm_checkbox)

        # Action Buttons
        self.action_category_label = QLabel("Action")
        self.action_category_label.setAlignment(Qt.AlignCenter)
        self.action_abdadd_button = QPushButton("Abduction/Adduction")
        self.action_abdadd_lateral_checkbox = QCheckBox("Lateral")
        self.action_flxext_button = QPushButton("Flexion/Extension")
        self.action_rotation_button = QPushButton("Rotation")
        self.action_return_button = QPushButton("Return to Landing Page")
        self.action_abdadd_button.clicked.connect(lambda: self.handle_analysis("abdadd"))
        self.action_flxext_button.clicked.connect(lambda: self.handle_analysis("flxext"))
        self.action_rotation_button.clicked.connect(lambda: self.handle_analysis("rotation"))
        self.action_return_button.clicked.connect(self.handle_return_to_landing_page)
        motion_flxext_group = QHBoxLayout(self)
        motion_flxext_group.addWidget(self.action_abdadd_button, 3)
        motion_flxext_group.addWidget(self.action_abdadd_lateral_checkbox, 1)
        motion_category_layout = QVBoxLayout()
        motion_category_layout.addLayout(motion_flxext_group)
        motion_category_layout.addWidget(self.action_flxext_button)
        motion_category_layout.addWidget(self.action_rotation_button)
        motion_category_layout.addWidget(self.action_return_button)

        # Analyzer Settings Layout
        analyzer_settings_layout = QGridLayout()
        analyzer_settings_layout.addWidget(self.model_choice_label, 0, 0)
        analyzer_settings_layout.addLayout(model_choice_layout, 1, 0)
        analyzer_settings_layout.addWidget(self.option_label, 0, 1)
        analyzer_settings_layout.addLayout(options_layout, 1, 1)
        analyzer_settings_layout.addWidget(self.body_part_label, 0, 2)
        analyzer_settings_layout.addLayout(body_part_selection_layout, 1, 2)
        analyzer_settings_layout.addWidget(self.action_category_label, 0, 3)
        analyzer_settings_layout.addLayout(motion_category_layout, 1, 3)
        # Set equal column stretch factors
        analyzer_settings_layout.setColumnStretch(0, 1)
        analyzer_settings_layout.setColumnStretch(1, 1)
        analyzer_settings_layout.setColumnStretch(2, 1)
        analyzer_settings_layout.setColumnStretch(3, 1)
        self.analyzer_settings_layout_container = QWidget()
        self.analyzer_settings_layout_container.setLayout(analyzer_settings_layout)

        # Plot Settings
        self.start_time_label = QLabel("Start Time (in sec)")
        self.end_time_label = QLabel("End Time (in sec)")
        self.start_time_input = QLineEdit()
        self.start_time_input.setMaximumWidth(100)
        self.start_time_input.setText("1")
        self.end_time_input = QLineEdit()
        self.end_time_input.setMaximumWidth(100)
        self.end_time_input.setText("5")

        self.fps_label = QLabel("Frame Rate (in Hz)")
        self.fps_input = QLineEdit()
        self.fps_input.setMaximumWidth(100)
        self.fps_input.editingFinished.connect(self.change_fps)

        self.threshold_max_label = QLabel("Threshold max (in deg)")
        self.threshold_min_label = QLabel("Threshold min (in deg)")
        self.threshold_max_input = QLineEdit()
        self.threshold_max_input.setMaximumWidth(100)
        self.threshold_min_input = QLineEdit()
        self.threshold_min_input.setMaximumWidth(100)

        self.limit_max_label = QLabel("Limit max")
        self.limit_min_label = QLabel("Limit min")
        self.limit_min_input = QLineEdit()
        self.limit_min_input.setMaximumWidth(100)
        self.limit_max_input = QLineEdit()
        self.limit_max_input.setMaximumWidth(100)

        self.zoom_start_label = QLabel("Zoom Start (in sec)")
        self.zoom_end_label = QLabel("Zoom End (in sec)")
        self.zoom_start_input = QLineEdit()
        self.zoom_start_input.setMaximumWidth(100)
        self.zoom_end_input = QLineEdit()
        self.zoom_end_input.setMaximumWidth(100)

        # Plot Settings Layouts
        plot_settings_layout = QGridLayout()
        plot_settings_layout.addWidget(self.start_time_label, 0, 0)
        plot_settings_layout.addWidget(self.start_time_input, 0, 1)
        plot_settings_layout.setColumnStretch(2, 1)  # Spacer column
        plot_settings_layout.addWidget(self.end_time_label, 0, 3)
        plot_settings_layout.addWidget(self.end_time_input, 0, 4)
        plot_settings_layout.setColumnStretch(5, 1)  # Spacer column
        plot_settings_layout.addWidget(self.fps_label, 0, 6)
        plot_settings_layout.addWidget(self.fps_input, 0, 7)
        plot_settings_layout.addWidget(self.threshold_min_label, 1, 0)
        plot_settings_layout.addWidget(self.threshold_min_input, 1, 1)
        plot_settings_layout.addWidget(self.threshold_max_label, 1, 3)
        plot_settings_layout.addWidget(self.threshold_max_input, 1, 4)
        plot_settings_layout.addWidget(self.zoom_start_label, 2, 0)
        plot_settings_layout.addWidget(self.zoom_start_input, 2, 1)
        plot_settings_layout.addWidget(self.zoom_end_label, 2, 3)
        plot_settings_layout.addWidget(self.zoom_end_input, 2, 4)
        plot_settings_layout.addWidget(self.limit_min_label, 3, 0)
        plot_settings_layout.addWidget(self.limit_min_input, 3, 1)
        plot_settings_layout.addWidget(self.limit_max_label, 3, 3)
        plot_settings_layout.addWidget(self.limit_max_input, 3, 4)
        self.plot_settings_layout_container = QWidget()
        self.plot_settings_layout_container.setLayout(plot_settings_layout)

        # Main Result Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(video_plots_layout, 1)
        self.main_layout.addLayout(landing_layout)
        self.main_layout.addWidget(self.analyzer_settings_layout_container)
        self.main_layout.addWidget(self.plot_settings_layout_container)

        # main window settings
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(self.main_layout)
        self.reset_gui()

    def reset_gui(self):
        self.open_file_action.setEnabled(True)
        self.save_slices_action.setEnabled(False)
        self.save_excel_action.setEnabled(False)
        self.save_plots_action.setEnabled(False)

        self.video_change_mode(VideoMode.FULL)
        self.video_change_playing_state(VideoState.PAUSED)
        self.video_widget.hide()
        self.video_play_button.hide()
        self.video_change_mode_button.hide()
        self.video_timestamp_padding = -1 # Padding applied to the video timestamp label when the video is in crop mode
        self.video_timestamp_label.hide()
        self.video_seekbar_slider.hide()
        self.generated_plots_label.hide()
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if isinstance(item, QSpacerItem):
                self.main_layout.removeItem(item)
                break

        self.is_on_rubber_band_widget = False
        self.rubber_band_widget.hide_rubber_band()
        self.rubber_band_widget.hide()
        self.video_select_area_button.hide()

        self.model_id_used = PoseModel.ALPHA_POSE
        self.alphapose_previously_processed = False
        self.mmpose_previously_processed = False
        self.repnet_previously_processed = False
        self.analyzer_settings_layout_container.hide()

        self.start_time_input.setText("1")
        self.end_time_input.setText("5")
        self.fps_input.clear()
        self.threshold_min_input.clear()
        self.threshold_max_input.clear()
        self.zoom_start_input.clear()
        self.zoom_end_input.clear()
        self.limit_max_input.clear()
        self.limit_min_input.clear()
        self.plot_settings_layout_container.hide()

        self.show_landing_page()

    def show_landing_page(self):
        self.landing_image_label.show()
        self.landing_open_button.show()

    def hide_landing_page(self):
        self.landing_image_label.hide()
        self.landing_open_button.hide()

    def handle_save_plots_action(self):
        x_pos = int(self.rubber_band_widget.band.pos().x())
        y_pos = int(self.rubber_band_widget.band.pos().y())
        width = int(self.rubber_band_widget.band.size().width())
        height = int(self.rubber_band_widget.band.size().height())

        source_path = os.path.join(
            Paths.RESULTS_RESULTS,
            os.path.basename(self.filename),
            f"{x_pos}{y_pos}{width}{height}",
            self.analysis_name
        )

        velocity_path = f"{source_path}Vitesse"
        fusion_path = f"{source_path}Fusion"

        save_folder, _ = QFileDialog.getSaveFileName(
            self, "Save Motion Analysis Plots", os.path.expanduser("~")
        )

        if save_folder:
            save_folder = add_date_time_to_path(save_folder)
            os.makedirs(save_folder, exist_ok=True)

            # Copy all PNG files from source path
            for png_file in [f for f in os.listdir(source_path) if f.lower().endswith('.png')]:
                shutil.copy(os.path.join(source_path, png_file), save_folder)

            # Copy all PNG files from velocity path if it exists
            if os.path.exists(velocity_path):
                for png_file in [f for f in os.listdir(velocity_path) if f.lower().endswith('.png')]:
                    shutil.copy(os.path.join(velocity_path, png_file), save_folder)

            # Copy all PNG files from fusion path if it exists
            if os.path.exists(fusion_path):
                for png_file in [f for f in os.listdir(fusion_path) if f.lower().endswith('.png')]:
                    shutil.copy(os.path.join(fusion_path, png_file), save_folder)

    def handle_save_excel_action(self):
        x_pos = int(self.rubber_band_widget.band.pos().x())
        y_pos = int(self.rubber_band_widget.band.pos().y())
        width = int(self.rubber_band_widget.band.size().width())
        height = int(self.rubber_band_widget.band.size().height())

        source_path = os.path.join(
            Paths.RESULTS_RESULTS,
            os.path.basename(self.filename),
            f"{x_pos}{y_pos}{width}{height}"
        )

        save_folder, _ = QFileDialog.getSaveFileName(
            self, "Save Motion Analysis Excel", os.path.expanduser("~")
        )

        if save_folder:
            save_folder = add_date_time_to_path(save_folder)
            os.makedirs(save_folder, exist_ok=True)

            # Copy all Excel files from source path
            for excel_file in [f for f in os.listdir(source_path) if f.lower().endswith('.xlsx')]:
                shutil.copy(os.path.join(source_path, excel_file), save_folder)

    def handle_save_slices_action(self):
        source_path = Paths.DATA_IMS

        save_folder, _ = QFileDialog.getSaveFileName(
            self, "Save Motion Analysis Slices", os.path.expanduser("~")
        )

        if save_folder:
            save_folder = add_date_time_to_path(save_folder)
            os.makedirs(save_folder, exist_ok=True)

            # Copy all image files from source path
            for image_file in [f for f in os.listdir(source_path) if f.lower().endswith(('.jpg'))]:
                shutil.copy(os.path.join(source_path, image_file), save_folder)

    def handle_exit_action(self):
        exit()

    def update_username(self, username):
        self.username = username

    def handle_model_checkboxes(self):
        # In case some are disabled from the body part checkboxes
        self.action_abdadd_button.setEnabled(True)
        self.action_abdadd_lateral_checkbox.setEnabled(True)
        self.action_flxext_button.setEnabled(True)
        self.action_rotation_button.setEnabled(True)

        self.head_checkbox.setChecked(True)
        self.shoulder_checkbox.setEnabled(True)
        self.torso_checkbox.setEnabled(True)
        self.arm_checkbox.setEnabled(True)
        self.forearm_checkbox.setEnabled(True)
        if self.alphapose_checkbox.isChecked():
            self.model_id_used = PoseModel.ALPHA_POSE
        if self.mmpose_checkbox.isChecked():
            self.model_id_used = PoseModel.MM_POSE
        if self.repnet_checkbox.isChecked():
            self.model_id_used = PoseModel.REP_NET
            self.shoulder_checkbox.setDisabled(True)
            self.torso_checkbox.setDisabled(True)
            self.arm_checkbox.setDisabled(True)
            self.forearm_checkbox.setDisabled(True)

    def handle_delete_last(self):
        if self.option_delete_last_checkbox.isEnabled() == True:
            if os.path.exists(self.last_path_ims_to_delete):
                shutil.rmtree(self.last_path_ims_to_delete)

    def handle_body_part_checkboxes(self):
        self.action_abdadd_button.setEnabled(False)
        self.action_abdadd_lateral_checkbox.setEnabled(False)
        self.action_flxext_button.setEnabled(False)
        self.action_rotation_button.setEnabled(False)
        if self.head_checkbox.isChecked():
            self.action_abdadd_button.setEnabled(True)
            self.action_abdadd_lateral_checkbox.setEnabled(True)
            self.action_flxext_button.setEnabled(True)
            self.action_rotation_button.setEnabled(True)
        elif self.shoulder_checkbox.isChecked():
            self.action_abdadd_button.setEnabled(True)
            self.action_flxext_button.setEnabled(True)
        elif self.torso_checkbox.isChecked():
            self.action_abdadd_button.setEnabled(True)
            self.action_flxext_button.setEnabled(True)
            self.action_rotation_button.setEnabled(True)
        elif self.arm_checkbox.isChecked():
            self.action_abdadd_button.setEnabled(True)
            self.action_abdadd_lateral_checkbox.setEnabled(True)
            self.action_flxext_button.setEnabled(True)
        elif self.forearm_checkbox.isChecked():
            self.action_flxext_button.setEnabled(True)

    def verify_start_and_end_inputs(self):
        if not self.start_time_input.text() or not self.end_time_input.text():
            QMessageBox.warning(self, "Input Error", "Both start time and end time must be provided.")
            return False

        try:
            start_time = float(self.start_time_input.text())
            end_time = float(self.end_time_input.text())

            if start_time >= end_time:
                QMessageBox.warning(self, "Input Error", "End time must be greater than start time.")
                return False
            video_duration = 0
            if self.filename:
                cap = cv2.VideoCapture(self.filename)
                if cap.isOpened():
                    # Get frame count and fps to calculate duration in seconds
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    video_duration = frame_count / fps
                    cap.release()
            if start_time < 0 or end_time > video_duration:
                QMessageBox.warning(self, "Input Error", "Start time and end time must be within the video duration.")
                return False
            if end_time - start_time < 2:
                QMessageBox.warning(self, "Input Error", "Cannot analyze less than 2 seconds of video.")
                return False
            if end_time - start_time > constants.MAX_CLIP_LENGTH:
                QMessageBox.warning(self, "Input Error", f"Cannot analyze more than {constants.MAX_CLIP_LENGTH} seconds (5 minutes) of video.")
                return False
            return True
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Start time and end time must be valid numbers.")
            return False

    def verify_fps_inputs(self):
        if not self.fps_input.text():
            QMessageBox.warning(self, "Input Error", "Frame rate must be provided.")
            return False

        try:
            fps = int(self.fps_input.text())
            if fps <= 0:
                QMessageBox.warning(self, "Input Error", "Frame rate must be a positive integer.")
                return False
            return True
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Frame rate must be a valid number.")
            return False

    def verify_threshold_inputs(self):
        # Case 1: No threshold inputs - always valid
        if not self.threshold_min_input.text() and not self.threshold_max_input.text():
            return True

        # Case 2: Both threshold inputs provided
        if self.threshold_min_input.text() and self.threshold_max_input.text():
            try:
                threshold_min = float(self.threshold_min_input.text())
                threshold_max = float(self.threshold_max_input.text())

                if threshold_min >= threshold_max:
                    QMessageBox.warning(self, "Input Error", "Threshold min must be less than Threshold max.")
                    return False
                return True
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Threshold values must be valid numbers.")
                return False

        # Case 3: Only one threshold input provided
        try:
            if self.threshold_min_input.text():
                threshold_min = float(self.threshold_min_input.text())
            if self.threshold_max_input.text():
                threshold_max = float(self.threshold_max_input.text())
            return True
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Threshold values must be valid numbers.")
            return False

    def verify_zoom_inputs(self):
        start_time = None
        end_time = None
        zoom_start = None
        zoom_end = None

        # Get start and end times for validation bounds
        try:
            if self.start_time_input.text() and self.end_time_input.text():
                start_time = float(self.start_time_input.text())
                end_time = float(self.end_time_input.text())
        except ValueError:
            # This should be caught by verify_start_and_end_inputs, so we don't need to handle it here
            pass

        # Case 1: No zoom inputs - always valid
        if not self.zoom_start_input.text() and not self.zoom_end_input.text():
            return True

        # Case 2: Both zoom inputs provided
        if self.zoom_start_input.text() and self.zoom_end_input.text():
            try:
                zoom_start = float(self.zoom_start_input.text())
                zoom_end = float(self.zoom_end_input.text())

                if zoom_start >= zoom_end:
                    QMessageBox.warning(self, "Input Error", "Zoom end must be greater than Zoom start.")
                    return False

                # Check if zoom values are within start/end time range
                if start_time is not None and end_time is not None:
                    if zoom_start < start_time or zoom_end > end_time:
                        QMessageBox.warning(self, "Input Error",
                                             "Zoom values must be within the start and end time range.")
                        return False
                return True
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Zoom values must be valid numbers.")
                return False

        # Case 3: Only one zoom input provided
        try:
            if self.zoom_start_input.text():
                zoom_start = float(self.zoom_start_input.text())
                # If we have start_time and end_time, verify zoom_start is within range
                if start_time is not None and end_time is not None:
                    if zoom_start < start_time or zoom_start > end_time:
                        QMessageBox.warning(self, "Input Error", "Zoom start must be within the start and end time range.")
                        return False

            if self.zoom_end_input.text():
                zoom_end = float(self.zoom_end_input.text())
                # If we have start_time and end_time, verify zoom_end is within range
                if start_time is not None and end_time is not None:
                    if zoom_end < start_time or zoom_end > end_time:
                        QMessageBox.warning(self, "Input Error", "Zoom end must be within the start and end time range.")
                        return False

            return True
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Zoom values must be valid numbers.")
            return False

    def verify_limit_inputs(self):
        # Case 1: No limit inputs - always valid
        if not self.limit_min_input.text() and not self.limit_max_input.text():
            return True

        # Case 2: Both limit inputs provided
        if self.limit_min_input.text() and self.limit_max_input.text():
            try:
                limit_min = float(self.limit_min_input.text())
                limit_max = float(self.limit_max_input.text())

                if limit_min >= limit_max:
                    QMessageBox.warning(self, "Input Error", "Limit min must be less than Limit max.")
                    return False
                return True
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Limit values must be valid numbers.")
                return False

        # Case 3: Only one limit input provided
        try:
            if self.limit_min_input.text():
                limit_min = float(self.limit_min_input.text())
            if self.limit_max_input.text():
                limit_max = float(self.limit_max_input.text())
            return True
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Limit values must be valid numbers.")
            return False

    def update_loading_time(self):
        self.loading_seconds += 1
        self.loading_label.setText(f"Processing... {self.loading_seconds} seconds elapsed")
        if self.expected_duration > 0:
            progress = min(100, int((self.loading_seconds / self.expected_duration) * 100))
            self.progress_bar.setValue(progress)
        self.status_label.setText(mc.current_analysis_step)
        QApplication.processEvents()

    def open_loading_screen(self):
        try:
            start_time = float(self.start_time_input.text())
            end_time = float(self.end_time_input.text())
            self.expected_duration = (end_time - start_time) * 4  # Assuming 4 seconds of processing time per second of video
        except (ValueError, AttributeError):
            self.expected_duration = 60

        self.loading_screen = QDialog(self)
        self.loading_screen.setWindowTitle("Analysis in Progress")
        self.loading_screen.setWindowModality(Qt.ApplicationModal)
        self.loading_screen.setMinimumWidth(400)

        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.update_loading_time)
        self.loading_seconds = 0
        self.loading_timer.start(1000)  # Update every second
        self.loading_label = QLabel("Processing... 0 seconds elapsed")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Waiting...")

        layout = QVBoxLayout()
        layout.addWidget(self.loading_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        self.loading_screen.setLayout(layout)

        # These flags make it impossible for the user to close the dialog
        self.loading_screen.setWindowFlags(
            Qt.Dialog |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint
        )

        self.loading_screen.show()
        QApplication.processEvents()  # Non-blocking call to allow the UI to update

    def close_loading_screen(self):
        self.loading_timer.stop()
        self.loading_screen.close()

    def handle_analysis(self, analysis_type):
        if not self.verify_start_and_end_inputs() \
        or not self.verify_threshold_inputs() \
        or not self.verify_zoom_inputs() \
        or not self.verify_limit_inputs():
            return

        self.video_change_playing_state(VideoState.PAUSED)
        self.video_timestamp_padding = float(self.start_time_input.text())
        mc.current_analysis_step = "Starting analysis..."
        self.open_loading_screen()
        self.analysis_type = analysis_type  # Store the analysis type for later use

        # Start analysis in a separate thread based on analysis type and selected body part
        if analysis_type == "abdadd":
            if self.head_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_head_abdadd,)).start()
            elif self.shoulder_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_shoulder_abdadd,)).start()
            elif self.torso_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_torso_abdadd,)).start()
            elif self.arm_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_arm_abdadd,)).start()
            else:
                QMessageBox.critical(self, "Motion selection Error", "Unrecognized abduction/adduction motion, you may have just selected a motion not available in the current version of the software.")
                self.close_loading_screen()
        elif analysis_type == "flxext":
            if self.head_checkbox.isChecked() and not self.action_abdadd_lateral_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_head_flxext,)).start()
            elif self.head_checkbox.isChecked() and self.action_abdadd_lateral_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_head_lateral_flxext,)).start()
            elif self.shoulder_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_shoulder_flxext,)).start()
            elif self.torso_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_torso_flxext,)).start()
            elif self.arm_checkbox.isChecked() and not self.action_abdadd_lateral_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_arm_flxext,)).start()
            elif self.arm_checkbox.isChecked() and self.action_abdadd_lateral_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_arm_lateral_flxext,)).start()
            elif self.forearm_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_forearm_flxext,)).start()
            else:
                QMessageBox.critical(self, "Motion selection Error", "Unrecognized flexion/extension motion, you may have just selected a motion not available in the current version of the software.")
                self.close_loading_screen()
        elif analysis_type == "rotation":
            if self.head_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_head_rotation,)).start()
            elif self.torso_checkbox.isChecked():
                Thread(target=self.run_analysis, args=(self.analyze_torso_rotation,)).start()
            else:
                QMessageBox.critical(self, "Motion selection Error", "Unrecognized rotation motion, you may have just selected a motion not available in the current version of the software.")
                self.close_loading_screen()
        else:
            QMessageBox.critical(self, "Motion selection Error", "Unrecognized motion type, you may have just selected a motion not available in the current version of the software.")
            self.close_loading_screen()

    def run_analysis(self, analysis_function):
        try:
            result = analysis_function()
            if result is None or len(result) != 4:
                # Post an error event to the main thread
                error_msg = "Invalid analysis result. The analysis function didn't return expected data."
                QApplication.instance().postEvent(self, AnalysisErrorEvent(error_msg))
                return

            # Store the result for processing in the main thread
            self.analysis_result = result
            # Post a success event to the main thread
            QApplication.instance().postEvent(self, AnalysisCompleteEvent())
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in analysis: {e}\n{error_details}")
            # Post an error event to the main thread with detailed exception info
            error_msg = f"Error in analysis: {str(e)}"
            QApplication.instance().postEvent(self, AnalysisErrorEvent(error_msg, error_details))

    def event(self, event):
        if event.type() == QEvent.User + 1:  # Analysis complete
            try:
                arg1, arg2, arg3, arg4 = self.analysis_result
                self.process_and_visualize_motion_data(arg1, arg2, arg3, arg4)
                self.close_loading_screen()
                self.video_change_mode(VideoMode.CROPPED)
                self.video_change_playing_state(VideoState.PLAYING)

                # Show a success message
                QMessageBox.information(
                    self,
                    "Analysis Complete",
                    "Motion analysis has been successfully completed."
                )
                return True
            except Exception as e:
                self.close_loading_screen()
                QMessageBox.critical(
                    self,
                    "Processing Error",
                    f"Error processing analysis results: {str(e)}"
                )
                return True

        elif event.type() == QEvent.User + 2:  # Analysis error
            self.close_loading_screen()

            # Create a detailed error message box
            error_box = QMessageBox(self)
            error_box.setWindowTitle("Analysis Error")
            error_box.setIcon(QMessageBox.Critical)
            error_box.setText(event.error_message)

            # If we have exception details, add them to a detailed text area
            if event.exception:
                error_box.setDetailedText(str(event.exception))

            # Add helpful information for the user
            error_box.setInformativeText(
                "Please check your input parameters and try again.\n"
                "You may want to try a different area selection or model."
            )

            error_box.exec_()
            return True

        elif event.type() == QEvent.User + 3:  # Model error
            self.close_loading_screen()

            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Warning)
            error_dialog.setWindowTitle("Model Error")
            error_dialog.setText(f"The {event.model_type} model didn't return any results.")
            error_dialog.setInformativeText("Please try again or select a different area/model.")
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.exec_()
            return True

        return super().event(event)

    def handle_return_to_landing_page(self):
        confirmation = QMessageBox.question(
            self,
            "Confirmation",
            "Are you sure you want to return to the landing page?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirmation == QMessageBox.Yes:
            self.reset_gui()

    def handle_position_changed(self, position):
        # position is the amount of time in milliseconds since start of video
        self.video_seekbar_slider.setValue(position)
        if not self.is_long_video_mode:
            position += self.video_timestamp_padding * 1000
        minutes = int(position / 60000)
        seconds = int((position / 1000) % 60)
        hundredths = int((position / 10) % 100)
        formatted_time = f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"
        self.video_timestamp_label.setText(f"{formatted_time}")

    def handle_duration_changed(self, duration):
        self.video_seekbar_slider.setRange(0, duration)

    def handle_video_seekbar(self, position):
        self.video_change_playing_state(VideoState.PAUSED)
        self.video_media_player.setPosition(position)
        if self.is_on_rubber_band_widget:
            self.video_save_frame(position)
            if os.path.exists("current_video_thumbnail.png"):
                self.rubber_band_widget.video_frame_label.setPixmap(QPixmap("current_video_thumbnail.png"))
            else:
                print("Error: Thumbnail image not found")

    def video_change_mode(self, state):
        if state == VideoMode.FULL:
            self.is_long_video_mode = True
            self.video_change_mode_button.setText("Change to cropped clip")
            media_url = QUrl.fromLocalFile(self.filename)
        elif state == VideoMode.CROPPED:
            self.is_long_video_mode = False
            self.video_change_mode_button.setText("Change to full video")
            media_url = QUrl.fromLocalFile(Paths.DATA_BUFFER)
        else:
            # This should not happen
            print("Error: Invalid video mode")
            return
        self.video_media_player.setMedia(QMediaContent(media_url))
        self.video_position_on_seekbar = 0
        self.video_change_playing_state(VideoState.PAUSED)

    def video_save_frame(self, position):
        video = cv2.VideoCapture(self.filename)
        if not video.isOpened():
            print("Error: Could not open video file")
            return
        video_fps = video.get(cv2.CAP_PROP_FPS)
        frame_id = int(video_fps * position / 1000)
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = video.read()
        if ret and frame is not None:
            cv2.imwrite("current_video_thumbnail.png", frame)
        else:
            print("Error: Could not read frame from video")
        video.release()

    def video_change_playing_state(self, state):
        if state == VideoState.PLAYING:
            self.video_media_player.play()
            self.video_play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.video_state = VideoState.PLAYING
        elif state == VideoState.PAUSED:
            self.video_media_player.pause()
            self.video_play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.video_state = VideoState.PAUSED
        else:
            # This should not happen
            print("Error: Invalid video state")

    def change_fps(self):
        if not self.verify_fps_inputs():
            self.fps = mc.get_frame_rate(self.filename)
            self.fps_input.clear()
            return
        original_fps = mc.get_frame_rate(self.filename)
        self.fps = int((int(self.fps_input.text()) * original_fps) / 60)  # TODO: check if this is correct, looks weird

    def handle_open_file_action(self):
        self.reset_gui()
        self.hide_landing_page()
        if self.open_file():
            self.show_landing_page()
            return

    def open_file(self):
        self.filename, _ = QFileDialog.getOpenFileName(
            self, "Open Video to Analyse", QDir.homePath()
        )
        if self.filename == "":
            # User canceled file selection
            return 1

        cap = cv2.VideoCapture(self.filename)
        if not cap.isOpened():
            QMessageBox.critical(self, "Error", "Could not open the video file.")
            return 1

        if cap.get(cv2.CAP_PROP_FRAME_HEIGHT) != 570:
            split = self.filename.split(".")
            scaled_video_name = split[0] + "_570p." + split[1]
            # Calculate new width that's divisible by 2 (required for some video codecs)
            scaling_factor = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) / 570
            new_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) / scaling_factor)
            new_width -= new_width % 2  # Ensures width is even
            input_vid = ffmpeg.input(self.filename)
            try:
                vid = (
                    input_vid.filter("scale", new_width, 570, -1)
                    .output(scaled_video_name)
                    .overwrite_output()
                    .run()
                )
                self.filename = scaled_video_name
            except Exception as e:
                print(f"Error during video processing: {e}")
                return 1

        self.video_change_mode(VideoMode.FULL)
        self.video_change_playing_state(VideoState.PAUSED)

        self.video_save_frame(0)
        self.is_on_rubber_band_widget = True
        self.rubber_band_widget.video_frame_label.setPixmap(QPixmap("current_video_thumbnail.png"))
        self.rubber_band_widget.video_frame_label.show()
        self.rubber_band_widget.show()
        self.video_seekbar_slider.show()
        self.video_select_area_button.show()
        self.main_layout.addStretch(1)  # Used to compress the rubberband into the video widget

    def get_crop_coords(self):
        self.fps = int(mc.get_frame_rate(self.filename))
        self.fps_input.setPlaceholderText(str(self.fps))

        band_pos = self.rubber_band_widget.band.pos()
        band_size = self.rubber_band_widget.band.size()
        self.top_left_coords_str = f"{int(band_pos.x())},{int(band_pos.y())}"
        self.bottom_right_coords_str = f"{int(band_pos.x() + band_size.width())},{int(band_pos.y() + band_size.height())}"
        self.video_widget.setMaximumSize(int(self.size().width()), int(self.size().height() / 1.50))

        self.is_on_rubber_band_widget = False
        self.rubber_band_widget.hide()
        self.video_select_area_button.hide()
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if isinstance(item, QSpacerItem):
                self.main_layout.removeItem(item)
                break

        self.video_widget.show()
        self.video_play_button.show()
        self.video_timestamp_label.show()
        self.video_seekbar_slider.show()

        self.option_label.setEnabled(False)
        self.option_delete_last_checkbox.setEnabled(False)
        self.option_show_limit_checkbox.setEnabled(False)
        self.analyzer_settings_layout_container.show()

        self.start_time_label.setEnabled(True)
        self.start_time_input.setEnabled(True)
        self.end_time_label.setEnabled(True)
        self.end_time_input.setEnabled(True)
        self.fps_label.setEnabled(True)
        self.fps_input.setEnabled(True)

        self.threshold_max_label.setEnabled(False)
        self.threshold_max_input.setEnabled(False)
        self.threshold_min_label.setEnabled(False)
        self.threshold_min_input.setEnabled(False)
        self.zoom_start_label.setEnabled(False)
        self.zoom_start_input.setEnabled(False)
        self.zoom_end_label.setEnabled(False)
        self.zoom_end_input.setEnabled(False)
        self.limit_max_label.setEnabled(False)
        self.limit_max_input.setEnabled(False)
        self.limit_min_label.setEnabled(False)
        self.limit_min_input.setEnabled(False)
        self.plot_settings_layout_container.show()

        self.video_change_mode(VideoMode.FULL)
        self.video_change_playing_state(VideoState.PLAYING)

    def process_and_visualize_motion_data(self, missing_joint_ids, motion_data, plot_color, motion_type):
        if motion_data is None or len(motion_data) < 2 or len(motion_data[0]) == 0:
            self.show_model_error()
            return

        self.video_change_mode_button.show()
        self.generated_plots_label.show()

        self.option_label.setEnabled(True)
        # self.option_delete_last_checkbox.setEnabled(True)  # TODO: currently removed from the things we want the app to do
        self.option_show_limit_checkbox.setEnabled(True)

        self.threshold_max_label.setEnabled(True)
        self.threshold_max_input.setEnabled(True)
        self.threshold_min_label.setEnabled(True)
        self.threshold_min_input.setEnabled(True)
        self.zoom_start_label.setEnabled(True)
        self.zoom_start_input.setEnabled(True)
        self.zoom_end_label.setEnabled(True)
        self.zoom_end_input.setEnabled(True)
        self.limit_max_label.setEnabled(True)
        self.limit_max_input.setEnabled(True)
        self.limit_min_label.setEnabled(True)
        self.limit_min_input.setEnabled(True)

        self.open_file_action.setEnabled(True)
        self.save_slices_action.setEnabled(True)
        self.save_excel_action.setEnabled(True)
        self.save_plots_action.setEnabled(True)

        # Used to skip the processing for a faster visualization if the parameters are the same
        self.previous_processed_data = [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]
        should_process_data = True

        # Handle limit input values for plotting
        try:
            if self.limit_max_input.text().strip() and self.limit_min_input.text().strip():
                lim_max_label = float(self.limit_max_input.text())
                lim_min_label = float(self.limit_min_input.text())
            else:
                # Default values when limits are not provided
                lim_max_label = -1000
                lim_min_label = -1000
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Limit values must be valid numbers."
            )
            lim_max_label = -1000
            lim_min_label = -1000

        # Get the coordinates of the cropped area
        x_pos = int(self.rubber_band_widget.band.pos().x())
        y_pos = int(self.rubber_band_widget.band.pos().y())
        width = int(self.rubber_band_widget.band.size().width())
        height = int(self.rubber_band_widget.band.size().height())
        cropped_coords_str = f"{x_pos}{y_pos}{width}{height}"

        # If previous results exist, move them to a backup folder
        check_path = os.path.join(
            Paths.RESULTS_RESULTS,
            os.path.basename(self.filename),
            cropped_coords_str
        )
        if os.path.exists(check_path):
            i = 1
            while os.path.exists(check_path + "_" + str(i)):
                i += 1
            backup_path = check_path + "_" + str(i)
            shutil.move(check_path, backup_path)
            QMessageBox.information(
                self,
                "Folder Backup",
                f"The previous result folder has been moved to {backup_path}.",
            )

        start_time = float(self.start_time_input.text())
        end_time = float(self.end_time_input.text())
        time_interval_id = f"{start_time}-{end_time}"

        zoom_start = float(self.zoom_end_input.text()) if self.zoom_end_input.text() else -1
        zoom_end = float(self.zoom_start_input.text()) if self.zoom_start_input.text() else -1

        # Apply limit to the data
        if self.limit_min_input.text() or self.limit_max_input.text():
            if self.limit_min_input.text():
                limit_min = float(self.limit_min_input.text())
            else:
                limit_min = -float('inf')
            if self.limit_max_input.text():
                limit_max = float(self.limit_max_input.text())
            else:
                limit_max = float('inf')
            motion_data = mc.apply_limit_to_data(motion_data, limit_min, limit_max)
        else:
            limit_min = -float('inf')
            limit_max = float('inf')

        if len(motion_data) > 2:
            y_max = max(max(motion_data[1]), max(motion_data[2]))
            y_min = min(min(motion_data[1]), min(motion_data[2]))
        else:
            y_max = max(motion_data[1])
            y_min = min(motion_data[1])

        # Handle threshold input values for plotting (-1000 = not used)
        threshold_max = float(self.threshold_max_input.text()) if self.threshold_max_input.text() else -1000
        threshold_min = float(self.threshold_min_input.text()) if self.threshold_min_input.text() else -1000

        numMax = 0
        if should_process_data:
            numMax, self.lastPathToDelete = mc.plotAndExcelSave(
                self.analysis_name,
                cropped_coords_str,
                plot_color,
                motion_data,
                self.filename,
                self.top_left_coords_str,
                self.bottom_right_coords_str,
                y_max,
                y_min,
                motion_type,
                self.option_show_limit_checkbox.isChecked(),
                lim_max_label,
                lim_min_label,
                zoom_start,
                zoom_end,
                threshold_max,
                threshold_min,
            )

            numberMax = mc.dirNumberMax(Paths.DATA_IMS_STOCK)
            self.last_path_ims_to_delete = os.path.join(Paths.DATA_IMS_STOCK, "ims" + str(numberMax))

            main_plot_path = os.path.join(
                Paths.RESULTS_RESULTS,
                os.path.basename(self.filename),
                cropped_coords_str,
                self.analysis_name,
                f"{time_interval_id}resPlot.png"
            )

            velocity_plot_path = os.path.join(
                Paths.RESULTS_RESULTS,
                os.path.basename(self.filename),
                cropped_coords_str,
                self.analysis_name + "Vitesse",
                f"{time_interval_id}resPlotV.png"
            )

            if os.path.exists(main_plot_path) and os.path.exists(velocity_plot_path):
                final_plot_folder_path = os.path.join(
                    Paths.RESULTS_RESULTS,
                    os.path.basename(self.filename),
                    cropped_coords_str,
                    self.analysis_name + "Fusion"
                )

                if not os.path.exists(final_plot_folder_path):
                    os.makedirs(final_plot_folder_path)

                mc.FusionImage(
                    main_plot_path,
                    velocity_plot_path,
                    self.analysis_name,
                    numMax,
                    os.path.basename(self.filename),
                    cropped_coords_str,
                    time_interval_id,
                )

        # Determine which image to display
        final_image = os.path.join(
            Paths.RESULTS_RESULTS,
            os.path.basename(self.filename),
            cropped_coords_str,
            self.analysis_name + "Fusion",
            time_interval_id + "Fus.png"
        )

        if ((missing_joint_ids == [18] and self.model_id_used == PoseModel.ALPHA_POSE)
            or (missing_joint_ids == [17] and self.model_id_used == PoseModel.MM_POSE)
            or self.model_id_used == PoseModel.REP_NET
        ) and os.path.exists(final_image):
            self.generated_plots_label.setPixmap(QPixmap(final_image))
        else:
            self.create_model_error_image(missing_joint_ids, self.model_id_used)
            self.generated_plots_label.setPixmap(QPixmap("model_error_image.png"))

    def create_model_error_image(self, option_indices, pose):
        if pose == PoseModel.ALPHA_POSE:
            options_data = [
                (0, " _ Nez"),
                (1, " _ Cou"),
                (2, " _ Épaule droite"),
                (3, " _ Coude droit"),
                (4, " _ Poignet droit"),
                (5, " _ Épaule gauche"),
                (6, " _ Coude gauche"),
                (7, " _ Poignet gauche"),
                (8, " _ Hanche droite"),
                (9, " _ Genou droit"),
                (10, " _ Cheville droite"),
                (11, " _ Hanche gauche"),
                (12, " _ Genou gauche"),
                (13, " _ Cheville gauche"),
                (14, " _ Œil droit"),
                (15, " _ Œil gauche"),
                (16, " _ Oreille droite"),
                (17, " _ Oreille gauche"),
                (
                    18,
                    " ERREUR   /!\\   Veuillez encadrer de plus les points corporels suivants : ",
                ),
            ]
        elif pose == PoseModel.MM_POSE:
            options_data = [
                (0, " _ Nez"),
                (1, " _ Œil gauche"),
                (2, " _ Œil droite"),
                (3, " _ Oreille gauche"),
                (4, " _ Oreille droite"),
                (5, " _ Epaule gauche"),
                (6, " _ Epaule droite"),
                (7, " _ Coude gauche"),
                (8, " _ Coude droite"),
                (9, " _ Poignet gauche"),
                (10, " _ Poignet droite"),
                (11, " _ Hanche gauche"),
                (12, " _ Hanche droite"),
                (13, " _ Genou gauche"),
                (14, " _ Genou droite"),
                (15, " _ Cheville gauche"),
                (16, " _ Cheville droite"),
                (
                    17,
                    " ERREUR   /!\\   Veuillez encadrer de plus les points corporels suivants : ",
                ),
            ]

        options = [options_data[idx][1] for idx in option_indices]

        # Créer une image blanche
        width, height = 800, 400
        background_color = (255, 255, 255)  # Blanc
        image = Image.new("RGB", (width, height), background_color)

        # Ouvrir un objet de dessin sur l'image
        draw = ImageDraw.Draw(image)

        # Texte à écrire
        text_red = (255, 0, 0)  # red
        text_black = (0, 0, 0)  # black

        image_font = ImageFont.truetype(Paths.ASSETS_FONT, 24)
        line_height = 30  # Hauteur de chaque ligne de texte

        # Coordonnées de départ pour la première ligne
        x = 20
        y = (height - (line_height * len(options))) // 2

        # Écrire chaque option
        j = 0
        for option in options:
            if j == 0:
                draw.text((x, y), option, fill=text_red, font=image_font)
            else:
                draw.text((x, y), option, fill=text_black, font=image_font)
            j = j + 1
            y += line_height

        # Enregistrer l'image avec le texte
        image.save("model_error_image.png")

    def show_model_error(parent, model_type="pose estimation"):
        # Instead of showing a message box directly, post an event
        QApplication.instance().postEvent(parent, ModelErrorEvent(model_type))

################################################################################
############################## FONCTION MOCAP ##################################
################################################################################

    def analyze_head_abdadd(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.head_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_abd_add(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_abd_add(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.REP_NET:
            if self.repnet_previously_processed == False:
                self.repnet_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_rp_abd_add(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("6DRepNet"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([229, 115, 115])
        self.analysis_name = "Abd_Add-head"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 11

    def analyze_head_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.head_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_nodding(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_nodding(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.REP_NET:
            if self.repnet_previously_processed == False:
                self.repnet_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_rp_nodding(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("6DRepNet"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([102, 210, 106])
        self.analysis_name = "Flex_Ext-head"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 12

    def analyze_head_rotation(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.head_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_rotation(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_rotation(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.REP_NET:
            if self.repnet_previously_processed == False:
                self.repnet_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_rp_rotation(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("6DRepNet"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([186, 104, 200])
        self.analysis_name = "Rot-head"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 13

    def analyze_head_lateral_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_lat_nod(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_lat_nod(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([102, 210, 106])
        self.analysis_name = "Flex_Ext-head_lat"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 14

    def analyze_shoulder_abdadd(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.shoulder_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_abd_add_shoul(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_abd_add_shoul(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([140, 193, 100])
        self.analysis_name = "Abd_Add-shoulder"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 21

    def analyze_shoulder_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.shoulder_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_shrugging(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_shrugging(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([240, 163, 10])
        self.analysis_name = "Flex_Ext-shoulder"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 22

    def analyze_torso_abdadd(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.torso_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_buste_abd_add(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_buste_abd_add(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([100, 100, 255])
        self.analysis_name = "Abd_Add-Torso"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 31

    def analyze_torso_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.torso_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_buste_flexion(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_buste_flexion(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([229, 100, 0])
        self.analysis_name = "Flex_Ext-Torso"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 32

    def analyze_torso_rotation(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.torso_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_buste_rotation(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_buste_rotation(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([150, 50, 200])
        self.analysis_name = "Rot-Torso"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 33

    def analyze_arm_abdadd(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.arm_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_arm_abduction(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_arm_abduction(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([80, 208, 255])
        self.analysis_name = "Abd_Add-arm"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 41

    def analyze_arm_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.arm_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_arm_flexion(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_arm_flexion(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([229, 20, 0])
        self.analysis_name = "Flex_Ext-arm"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 42

    def analyze_arm_lateral_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_arm_flexion_lat(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_arm_flexion_lat(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([229, 20, 0])
        self.analysis_name = "Flex_Ext-arm_lateral"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 43

    def analyze_forearm_flxext(self):
        QApplication.setOverrideCursor(self.cursor)
        if not (
            self.filename
            or self.start_time_input.text()
            or self.end_time_input.text()
            or self.forearm_checkbox.isChecked()
        ):
            QApplication.restoreOverrideCursor()
            return

        if self.previous_processed_data == [
            float(self.start_time_input.text()),
            float(self.end_time_input.text()),
            self.filename,
        ]:
            skip_motion_processing = True
        else:
            skip_motion_processing = False

        if self.model_id_used == PoseModel.ALPHA_POSE:
            if self.alphapose_previously_processed == False:
                self.alphapose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_ap_forearm_flexion(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("AlphaPose"))
                QApplication.restoreOverrideCursor()
                return

        elif self.model_id_used == PoseModel.MM_POSE:
            if self.mmpose_previously_processed == False:
                self.mmpose_previously_processed = True
                skip_motion_processing = False
            listErr, motion_data = mc.extractgraphs_mp_forearm_flexion(
                self.filename,
                float(self.start_time_input.text()),
                float(self.end_time_input.text()),
                self.fps,
                [
                    int(self.rubber_band_widget.band.pos().y()),
                    int(self.rubber_band_widget.band.pos().x()),
                    int(self.rubber_band_widget.band.size().height()),
                    int(self.rubber_band_widget.band.size().width()),
                ],
                skip_motion_processing,
                self.username,
            )
            if motion_data is None:
                QApplication.instance().postEvent(self, ModelErrorEvent("MMPose"))
                QApplication.restoreOverrideCursor()
                return

        plot_color = np.array([229, 20, 150])
        self.analysis_name = "Flex_Ext-forearm"
        QApplication.restoreOverrideCursor()
        return listErr, motion_data, plot_color, 44

def ensure_directories_exists():
    if not os.path.exists(Paths.DATA):
        os.makedirs(Paths.DATA, exist_ok=True)
        print(f"Created data directory at {Paths.DATA}")

    if not os.path.exists(Paths.RESULTS):
        os.makedirs(Paths.RESULTS, exist_ok=True)
        print(f"Created results directory at {Paths.RESULTS}")

    if not os.path.exists(Paths.RESULTS_RES):
        os.makedirs(Paths.RESULTS_RES, exist_ok=True)
        print(f"Created results/res directory at {Paths.RESULTS_RES}")

    if not os.path.exists(Paths.RESULTS_RESULTS):
        os.makedirs(Paths.RESULTS_RESULTS, exist_ok=True)
        print(f"Created results/results directory at {Paths.RESULTS_RESULTS}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ensure_directories_exists()
    video_player = VideoPlayer()
    video_player.resize(900, 600)
    video_player.show()
    video_player.account_manager.setWindowModality(Qt.ApplicationModal)
    video_player.account_manager.show()
    video_player.account_manager.raise_()
    sys.exit(app.exec_())
