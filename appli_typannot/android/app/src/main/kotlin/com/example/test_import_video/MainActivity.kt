package com.example.test_import_video

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarker
// import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.vision.core.RunningMode
import java.io.File

class MainActivity: FlutterActivity() {
    private val CHANNEL = "mediapipe_holistic"
    private var poseLandmarker: PoseLandmarker? = null
    // private var handLandmarker: HandLandmarker? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        initializeMediaPipe()
        
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "processVideo" -> {
                    val videoPath = call.argument<String>("videoPath")
                    val frameRate = call.argument<Int>("frameRate") ?: 24
                    if (videoPath != null) {
                        try{
                            val keypoints = processVideo(videoPath, frameRate)
                            result.success(keypoints)
                        } catch (e:Exception){
                            result.error("PROCESS_ERROR",e.message,null)
                        }
                    } else {
                        result.error("INVALID_ARGUMENT", "Video path is null", null)
                    }
                }
                "processFrame" -> {
                    val imageBytes = call.argument<ByteArray>("imageBytes")
                    if(imageBytes != null){
                        try{
                            val keypoints = processFrame(imageBytes)
                            result.success(keypoints)
                        } catch (e:Exception){
                            result.error("PROCESS_ERROR",e.message,null)
                        }
                    } else {
                        result.error("INVALID_ARGUMENT","Image bytes are null",null)
                    }
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun initializeMediaPipe(){

        try{

           // Initialisation Pose Landmarker
            val poseBaseOptions = BaseOptions.builder()
                .setModelAssetPath("pose_landmarker_heavy.task")
                .build()
            val poseOptions = PoseLandmarker.PoseLandmarkerOptions.builder()
                .setBaseOptions(poseBaseOptions)
                .setRunningMode(RunningMode.IMAGE)
                .setNumPoses(1)
                .build()
            poseLandmarker = PoseLandmarker.createFromOptions(this, poseOptions)

            /*
            // Initialisation Hand Landmarker
            val handBaseOptions = BaseOptions.builder()
                .setModelAssetPath("hand_landmarker.task")
                .build()
            val handOptions = HandLandmarker.HandLandmarkerOptions.builder()
                .setBaseOptions(handBaseOptions)
                .setRunningMode(RunningMode.IMAGE)
                .setNumHands(2)
                .build()
            handLandmarker = HandLandmarker.createFromOptions(this, handOptions)
            */
            
        } catch (e: Exception) {
            android.util.Log.e("MediaPipe", "Erreur d'initialisation: ${e.message}")
        }
    }

    private fun processVideo(videoPath: String, frameRate: Int): Map<String,Any>{

        val retriever = MediaMetadataRetriever()
        retriever.setDataSource(videoPath)

        val duration = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLong()?:0
        val frameInterval = 1000000L / frameRate

        val allFramesKeypoints = mutableListOf<Map<String,Any>>()
        var currentTime = 0L
        var frameIndex = 0

        android.util.Log.d("MediaPipe","Début extraction: ${duration}ms @ $ {frameRate} fps")

        while (currentTime<duration*1000){
            val originalBitmap = retriever.getFrameAtTime(currentTime, MediaMetadataRetriever.OPTION_CLOSEST)

            if (originalBitmap!= null){

                // Conversion RGB en ARGB_8888
                val bitmap = if (originalBitmap.config != Bitmap.Config.ARGB_8888) {
                    android.util.Log.e("MediaPipe", "🔄 Conversion vers ARGB_8888...")
                    val convertedBitmap = originalBitmap.copy(Bitmap.Config.ARGB_8888, false)
                    originalBitmap.recycle() // Libérer l'original
                    convertedBitmap
                } else {
                    originalBitmap
                }

                val keypoints = detectHolisticKeypoints(bitmap)
                allFramesKeypoints.add(mapOf(
                    "frameIndex" to frameIndex,
                    "timestamp" to currentTime/1000,
                    "keypoints" to keypoints
                ))
                frameIndex++
                bitmap.recycle()

                if (frameIndex % 50 == 0){
                    android.util.Log.d("Mediapipe","Progression: $frameIndex frames")
                }
            }
            currentTime += frameInterval
        }
        retriever.release()

        android.util.Log.d("Mediapipe","Extraction terminée!!! : $frameIndex frames")

        return mapOf(
            "totalFrames" to frameIndex,
            "duration" to duration,
            "frameRate" to frameRate,
            "frames" to allFramesKeypoints
        )
    }

    private fun processFrame(imageBytes: ByteArray): Map<String,Any>{
        val originalBitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
        
        
        // Conversion RGB en ARGB_8888
        val bitmap = if (originalBitmap.config != Bitmap.Config.ARGB_8888) {
            android.util.Log.d("MediaPipe", "🔄 Conversion frame: ${originalBitmap.config} → ARGB_8888")
            val convertedBitmap = originalBitmap.copy(Bitmap.Config.ARGB_8888, false)
            originalBitmap.recycle()
            convertedBitmap
        } else {
            originalBitmap
        }
        
        val result = detectHolisticKeypoints(bitmap)
        bitmap.recycle()
        return result
    }
    
    private fun detectHolisticKeypoints(bitmap:Bitmap):Map<String,Any>{
        val mpImage = BitmapImageBuilder(bitmap).build()
        val result = mutableMapOf<String,Any>()

        //Détection de pose
        poseLandmarker?.let { detector ->
            try{
                val poseResult = detector.detect(mpImage)
                val poseLandmarks = mutableListOf<Map<String,Any>>()

                poseResult.landmarks().forEach{ landmarkList->
                    landmarkList.forEachIndexed {index,landmark->
                        poseLandmarks.add(mapOf(
                            "index" to index,
                            "x" to landmark.x(),
                            "y" to landmark.y(),
                            "z" to landmark.z(),
                            "visibility" to (landmark.visibility().orElse(1.0f))
                        ))
                    }
                }
                result["pose"]=poseLandmarks
            } catch (e:Exception){
                android.util.Log.e("MediaPipe", "Erreur pose: ${e.message}")
                result["pose"] = emptyList<Map<String, Any>>()
            }
        }

        /*
        //Détection des mains
        handLandmarker?.let { detector ->
            try{
                val handResult = detector.detect(mpImage)
                val allHandsLandmarks = mutableListOf<Map<String,Any>>()

                handResult.landmarks().forEachIndexed{ handIndex,landmarkList ->
                    val handLandmarks = mutableListOf<Map<String,Any>>()
                    landmarkList.forEachIndexed{ index, landmark ->
                        handLandmarks.add(mapOf(
                            "index" to index,
                            "x" to landmark.x(),
                            "y" to landmark.y(),
                            "z" to landmark.z()
                        ))
                    }
                    allHandsLandmarks.add(mapOf(
                        "hand" to handIndex,
                        "handedness" to (handResult.handedness()[handIndex][0].categoryName()),
                        "landmarks" to handLandmarks
                    ))
                }
                result["hands"] = allHandsLandmarks
            } catch (e:Exception){
                android.util.Log.e("MediaPipe", "Erreur mains: ${e.message}")
                result["hands"] = emptyList<Map<String, Any>>()
            }
        }
        */

        return result

    }
    
    override fun onDestroy(){
        super.onDestroy()
        poseLandmarker?.close()
        //handLandmarker?.close()
    }
}