import Flutter
import AVFoundation
import UIKit
import MediaPipeTasksVision

@main
@objc class AppDelegate: FlutterAppDelegate {
  private var poseLandmarker: PoseLandmarker?

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    let controller: FlutterViewController = window?.rootViewController as! FlutterViewController
    let channel = FlutterMethodChannel(
      name: "mediapipe_holistic",
      binaryMessenger: controller.binaryMessenger
    )

    initializeMediaPipe()

    channel.setMethodCallHandler { [weak self] (call: FlutterMethodCall, result: @escaping FlutterResult) in
      switch call.method {
        case "processVideo":
          guard let args = call.arguments as? [String: Any],
                let videoPath = args["videoPath"] as? String else {
              result(FlutterError(code: "INVALID_ARGUMENT", message: "Video path is null", details: nil))
              return
          }
          // FIX 1: frameRate extrait ici et passé en paramètre à processVideo
          let frameRate = args["frameRate"] as? Int ?? 24
          do {
              let keypoints = try self?.processVideo(videoPath: videoPath, frameRate: frameRate)
              result(keypoints)
          } catch {
              result(FlutterError(code: "PROCESS_ERROR", message: error.localizedDescription, details: nil))
          }

        case "processFrame":
          guard let args = call.arguments as? [String: Any],
                let imageData = args["imageBytes"] as? FlutterStandardTypedData else {
              result(FlutterError(code: "INVALID_ARGUMENT", message: "Image bytes are null", details: nil))
              return
          }
          do {
              let keypoints = try self?.processFrame(imageData: imageData.data)
              result(keypoints)
          } catch {
              result(FlutterError(code: "PROCESS_ERROR", message: error.localizedDescription, details: nil))
          }

        default:
          result(FlutterMethodNotImplemented)
      }
    }

    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  private func initializeMediaPipe() {
    do {
      let poseModelPath = Bundle.main.path(forResource: "pose_landmarker_heavy", ofType: "task")!
        
      let poseOptions = PoseLandmarkerOptions()
      poseOptions.baseOptions.modelAssetPath = poseModelPath
      poseOptions.runningMode = .image
      poseOptions.numPoses = 1
      poseLandmarker = try PoseLandmarker(options: poseOptions)
      print("Initialisation MediaPipe ok")
    } catch {
      print("Erreur d'initialisation MediaPipe: \(error)")
    }
  }

  // FIX 2: frameRate ajouté comme paramètre de la fonction
  // FIX 3: type de retour corrigé [String:Any] au lieu de [String]
  private func processVideo(videoPath: String, frameRate: Int = 24) throws -> [String: Any] {
    let asset = AVAsset(url: URL(fileURLWithPath: videoPath))
    let duration = CMTimeGetSeconds(asset.duration) * 1000
    let frameInterval = 1.0 / Double(frameRate)

    var allFramesKeypoints: [[String: Any]] = []
    var currentTime = 0.0
    var frameIndex = 0

    let generator = AVAssetImageGenerator(asset: asset)
    // FIX 4: requestedTimePolicy remplacé par requestedTimeToleranceBefore/After
    generator.requestedTimeToleranceBefore = .zero
    generator.requestedTimeToleranceAfter = .zero

    print("Début extraction: \(duration)ms @ \(frameRate)fps")

    while currentTime < duration / 1000.0 {
      let time = CMTime(seconds: currentTime, preferredTimescale: 600)

      do {
        let cgImage = try generator.copyCGImage(at: time, actualTime: nil)
        let uiImage = UIImage(cgImage: cgImage)

        if let keypoints = try detectHolisticKeypoints(image: uiImage) {
          allFramesKeypoints.append([
            "frameIndex": frameIndex,
            "timestamp": Int(currentTime * 1000),
            "keypoints": keypoints
          ])
        }
        frameIndex += 1

        if frameIndex % 50 == 0 {
          print("Progression: \(frameIndex) frames")
        }
      } catch {
        print("Erreur extraction frame: \(error)")
      }

      currentTime += frameInterval
    }

    print("Extraction terminée!!: \(frameIndex) frames")

    return [
      "totalFrames": frameIndex,
      "duration": Int(duration),
      "frameRate": frameRate,
      "frames": allFramesKeypoints
    ]
  }

  private func processFrame(imageData: Data) throws -> [String: Any] {
    guard let uiImage = UIImage(data: imageData) else {
      throw NSError(domain: "MediaPipe", code: -1, userInfo: [NSLocalizedDescriptionKey: "Impossible de décoder l'image"])
    }
    return try detectHolisticKeypoints(image: uiImage) ?? [:]
  }

  private func detectHolisticKeypoints(image: UIImage) throws -> [String: Any]? {
    guard let mpImage = try? MPImage(uiImage: image) else {
      return nil
    }

    var result: [String: Any] = [:]

    if let detector = poseLandmarker {
      do {
        let poseResult = try detector.detect(image: mpImage)
        var poseLandmarks: [[String: Any]] = []

        // FIX 5: .first() (appel de fonction) remplacé par .first (propriété)
        // FIX 6: 'landmarks' renommé correctement depuis poseResult.landmarks.first
        if let landmarks = poseResult.landmarks.first {
          for (index, landmark) in landmarks.enumerated() {
            poseLandmarks.append([
              "index": index,
              "x": landmark.x,
              "y": landmark.y,
              "z": landmark.z,
              "visibility": landmark.visibility?.floatValue ?? 1.0
            ])
          }
        }
        result["pose"] = poseLandmarks
      } catch {
        print("Erreur pose: \(error)")
        result["pose"] = []
      }
    }

    return result
  }
}
