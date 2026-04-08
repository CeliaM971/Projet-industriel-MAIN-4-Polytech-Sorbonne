## Structure du projet (dossiers et fichiers principaux, les autres seront omis)

```
.
├── lib/                    
|   └── main.dart
|   └── mediapipe_bridge.dart
|   └── frontend
|       └── annotate_video.dart
|       └── group_manager.dart
|       └── group_selection_page.dart
|       └── homepage.dart
|       └── import_video.dart
|       └── library.dart
|       └── login.dart
|       └── logout.dart
|       └── plotting.dart
|       └── register.dart
|       └── saved_videos.dart
|       └── saved_videos_list_screen.dart
|       └── server.dart
|       └── squeleton_analysis.dart
|       └── user_profile.dart
|   └── backend
|       └── models
|           └── Annotation.py
|           └── TypannotCharacter.py
|           └── group.py
|           └── invitation.py
|           └── links.py
|           └── user.py
|           └── video.py
|       └── routers
|           └── Annotations.py
|           └── groups.py
|           └── invitations.py
|           └── typannot.py
|           └── users.py
|           └── videos.py
|       └── AlphaPose.py
|       └── Human_Coord.py
|       └── MMPose.py
|       └── User_database.py
|       └── constants.py
|       └── database.db
|       └── database.py
|       └── db.py
|       └── main.py
|       └── mocap1.py
|       └── mocap_gui1.py
|       └── models.py
|       └── requirements.txt
|       └── security.py
|       └──seedTypannot.py
|       └── setup.py
|   └── MediaPipe
|       └── constants.dart
|       └── mediapipe_service.dart
|       └── mocap1.dart
|       └── mocap_gui1.dart
├── android/                            #Configs spécifiques à android
|   └── app
|       └── src
|           └── main
|               └── kotlin/com/example/test_import_video
|                   └── MainActivity.kt
|               └── AndroidManifest.xml
|       └── build.gradle.kts
├── ios/                                #Configs spécifiques à ios
|    └── Podfile
|    └── Runner
|       └── AppDelegate.swif
|       └── Info.plist
|    └── Podfile
├── analysis_options.yaml
├── pubspec.yaml                
└── README.md
```