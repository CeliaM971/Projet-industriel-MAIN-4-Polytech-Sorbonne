// lib/mediapipe_bridge.dart
import 'package:flutter/services.dart';

class MediaPipeBridge {
  static const MethodChannel _channel = MethodChannel('mediapipe_vision');
  
  static Future<List<dynamic>> detectPose(Uint8List imageBytes) async {
    try {
      final result = await _channel.invokeMethod('detectPose', {
        'imageBytes': imageBytes,
      });
      return result;
    } catch (e) {
      print('Erreur: $e');
      return [];
    }
  }
}