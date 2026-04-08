import 'package:flutter/services.dart';
import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';

class MediaPipeService {
  static const MethodChannel _channel = MethodChannel('mediapipe_holistic');

  /// Traite une vidéo complète et retourne tous les keypoints
  static Future<HolisticVideoResult> processVideo(
    String videoPath, {
    int frameRate = 24,
    Function(double)? onProgress,
  }) async {
    try {
      final result = await _channel.invokeMethod('processVideo', {
        'videoPath': videoPath,
        'frameRate': frameRate,
      });

      return HolisticVideoResult.fromMap(result);
    } on PlatformException catch (e) {
      throw Exception('Erreur lors du traitement de la vidéo: ${e.message}');
    }
  }

  /// Traite une seule image et retourne les keypoints
  static Future<HolisticFrameResult> processFrame(Uint8List imageBytes) async {
    try {
      final result = await _channel.invokeMethod('processFrame', {
        'imageBytes': imageBytes,
      });

      return HolisticFrameResult.fromMap(result);
    } on PlatformException catch (e) {
      throw Exception('Erreur lors du traitement de l\'image: ${e.message}');
    }
  }

  /// Sauvegarde des résultats dans un fichier JSON
  static Future<File> saveResultsToJson(
    HolisticVideoResult results,
    String filename,
  ) async {
    final directory = await getApplicationDocumentsDirectory();
    final file = File('${directory.path}/$filename');
    
    final jsonString = json.encode(results.toJson());
    await file.writeAsString(jsonString);
    
    return file;
  }

  /// Charge les résultats depuis un fichier JSON
  static Future<HolisticVideoResult?> loadResultsFromJson(String filepath) async {
    try {
      final file = File(filepath);
      if (!await file.exists()) return null;
      
      final jsonString = await file.readAsString();
      final jsonData = json.decode(jsonString);
      
      return HolisticVideoResult.fromMap(jsonData);
    } catch (e) {
      print('Erreur chargement JSON: $e');
      return null;
    }
  }
}

/// Résultat pour une vidéo complète
class HolisticVideoResult {
  final int totalFrames;
  final int duration;
  final int frameRate;
  final List<FrameData> frames;

  HolisticVideoResult({
    required this.totalFrames,
    required this.duration,
    required this.frameRate,
    required this.frames,
  });

  factory HolisticVideoResult.fromMap(Map<dynamic, dynamic> map) {
    final framesList = (map['frames'] as List<dynamic>).map((frameMap) {
      return FrameData.fromMap(frameMap as Map<dynamic, dynamic>);
    }).toList();

    return HolisticVideoResult(
      totalFrames: map['totalFrames'] as int,
      duration: map['duration'] as int,
      frameRate: map['frameRate'] as int,
      frames: framesList,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'totalFrames': totalFrames,
      'duration': duration,
      'frameRate': frameRate,
      'frames': frames.map((f) => f.toJson()).toList(),
    };
  }

  /// Obtenir les keypoints d'une frame spécifique
  FrameData? getFrameAtIndex(int index) {
    if (index < 0 || index >= frames.length) return null;
    return frames[index];
  }

  /// Obtenir les keypoints au timestamp (en ms)
  FrameData? getFrameAtTime(int timestamp) {
    for (var frame in frames) {
      if (frame.timestamp >= timestamp) return frame;
    }
    return frames.isNotEmpty ? frames.last : null;
  }
}

/// Données d'une frame
class FrameData {
  final int frameIndex;
  final int timestamp;
  final HolisticFrameResult keypoints;

  FrameData({
    required this.frameIndex,
    required this.timestamp,
    required this.keypoints,
  });

  factory FrameData.fromMap(Map<dynamic, dynamic> map) {
    return FrameData(
      frameIndex: map['frameIndex'] as int,
      timestamp: map['timestamp'] as int,
      keypoints: HolisticFrameResult.fromMap(
        map['keypoints'] as Map<dynamic, dynamic>,
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'frameIndex': frameIndex,
      'timestamp': timestamp,
      'keypoints': keypoints.toJson(),
    };
  }
}

/// Résultat pour une seule frame
class HolisticFrameResult {
  final List<Landmark> pose;
  //final List<HandData> hands;

  HolisticFrameResult({
    required this.pose,
    //required this.hands,
  });

  factory HolisticFrameResult.fromMap(Map<dynamic, dynamic> map) {
    final poseList = (map['pose'] as List<dynamic>?)
            ?.map((l) => Landmark.fromMap(l as Map<dynamic, dynamic>))
            .toList() ??
        [];

    /*
    final handsList = (map['hands'] as List<dynamic>?)
            ?.map((h) => HandData.fromMap(h as Map<dynamic, dynamic>))
            .toList() ??
        [];
    */

    return HolisticFrameResult(
      pose: poseList,
      //hands: handsList,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'pose': pose.map((l) => l.toJson()).toList(),
      //'hands': hands.map((h) => h.toJson()).toList(),
    };
  }

  bool get hasDetections => pose.isNotEmpty ; // || hands.isNotEmpty

  //Getters pour faciliter l'accès au keypoints 

  Landmark get nose => pose[0];
  //Landmark get leftEyeInner => pose[1];
  Landmark get leftEye => pose[2];
  //Landmark get leftEyeOuter => pose[3];
  //Landmark get rightEyeInner => pose[4];
  Landmark get rightEye => pose[5];
  //Landmark get rightEyeOuter => pose[6];
  Landmark get leftEar => pose[7];
  Landmark get rightEar => pose[8];
  //Landmark get mouthLeft => pose[9];
  //Landmark get mouthRight => pose[10];
  Landmark get leftShoulder => pose[11];
  Landmark get rightShoulder => pose[12];
  Landmark get leftElbow => pose[13];
  Landmark get rightElbow => pose[14];
  Landmark get leftWrist => pose[15];
  Landmark get rightWrist => pose[16];
  //Landmark get leftPinky => pose[17];
  // Landmark get rightPinky => pose[18];
  //Landmark get leftIndex => pose[19];
  //Landmark get rightIndex => pose[20];
  //Landmark get leftThumb => pose[21];
  //Landmark get rightThumb => pose[22];
  Landmark get leftHip => pose[23];
  Landmark get rightHip => pose[24];
  Landmark get leftKnee => pose[25];
  Landmark get rightKnee => pose[26];
  Landmark get leftAnkle => pose[27];
  Landmark get rightAnkle => pose[28];
  //Landmark get leftHeel => pose[29];
  //Landmark get rightHeel => pose[30];
  //Landmark get leftFootIndex => pose[31];
  //Landmark get rightFootIndex => pose[33];



  //Calcul des keypoint mi-épaule et mi-hanche

  List<double> get midShoulder => [
    (leftShoulder.x + rightShoulder.x) /2,
    (leftShoulder.y + rightShoulder.y) /2,
  ];

  List<double> get midHip => [
    (leftHip.x + rightHip.x) /2,
    (leftHip.y + rightHip.y) /2,
  ];

}

/// Données d'une main
class HandData {
  final int hand;
  final String handedness;
  final List<Landmark> landmarks;

  HandData({
    required this.hand,
    required this.handedness,
    required this.landmarks,
  });

  factory HandData.fromMap(Map<dynamic, dynamic> map) {
    final landmarksList = (map['landmarks'] as List<dynamic>)
        .map((l) => Landmark.fromMap(l as Map<dynamic, dynamic>))
        .toList();

    return HandData(
      hand: map['hand'] as int,
      handedness: map['handedness'] as String,
      landmarks: landmarksList,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'hand': hand,
      'handedness': handedness,
      'landmarks': landmarks.map((l) => l.toJson()).toList(),
    };
  }

  bool get isLeft => handedness.toLowerCase().contains('left');
  bool get isRight => handedness.toLowerCase().contains('right');
}

/// Point de repère (landmark)
class Landmark {
  final int index;
  final double x;
  final double y;
  final double z;
  final double? visibility;

  Landmark({
    required this.index,
    required this.x,
    required this.y,
    required this.z,
    this.visibility,
  });

  factory Landmark.fromMap(Map<dynamic, dynamic> map) {
    return Landmark(
      index: map['index'] as int,
      x: (map['x'] as num).toDouble(),
      y: (map['y'] as num).toDouble(),
      z: (map['z'] as num).toDouble(),
      visibility: map['visibility'] != null
          ? (map['visibility'] as num).toDouble()
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'index': index,
      'x': x,
      'y': y,
      'z': z,
      if (visibility != null) 'visibility': visibility,
    };
  }

  bool get isVisible => visibility == null || visibility! > 0.5;
}

class MotionData {
  final List<double> times;
  final List<double> values;
  final List<double>? valuesLeft; // Pour mouvements bilatéraux
  final List<int> missingKeypoints; // Pour afficher les erreurs

  MotionData({
    required this.times,
    required this.values,
    this.valuesLeft,
    this.missingKeypoints = const [],
  });

  bool get isBilateral => valuesLeft != null && valuesLeft!.isNotEmpty;
}