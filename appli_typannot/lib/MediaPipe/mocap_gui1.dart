import 'mocap1.dart';
import 'constants.dart';
import 'mediapipe_service.dart';

class MocapController{

  // Etat
  PoseModel modelIdUsed = PoseModel.mediaPipe;
  BodyPart? selectedBodyPart;
  bool _deleteLastSlices = false;
  bool _includeLimitOfData = true;

  HolisticVideoResult? holisticResults;
  MotionData? currentMotionData;
  String analysisName = '';

  //Tests sur les options choisies par l'utilisateur
  bool verify_start_and_end_inputs({required double startTime, required double endTime, double? videoDuration}){
    if(startTime >= endTime){
      return false;
    }
    if(videoDuration != null){
      if(startTime<0 || endTime > videoDuration){
        return false;
      }
    }
    if (endTime-startTime<2){
      return false;
    }
    if(endTime - startTime > 300){ //5min
      return false;
    }
    return true;
  }

  bool verify_fps_inputs(String text){
    if (text.trim().isEmpty){
      return false;
    }
    final fps = int.tryParse(text);
    if(fps == null){
      return false;
    }
    if (fps<=0){
      return false;
    }
    return true;
  }

  bool verify_threshold_inputs({String? thresholdMinText, String? thresholdMaxText}){

    // Case 1: No threshold inputs - always valid
    if((thresholdMinText == null || thresholdMinText.isEmpty) && 
       (thresholdMaxText == null || thresholdMaxText.isEmpty)){
        return true;
       }

    // Case 2: Both threshold inputs provided
    if (thresholdMinText != null && thresholdMinText.isNotEmpty && thresholdMaxText != null && thresholdMaxText.isNotEmpty){
      try {
        double thresholdMin = double.parse(thresholdMinText);
        double thresholdMax = double.parse(thresholdMaxText);

        if (thresholdMin >= thresholdMax){
          return false;
        }
        return true;
      } catch(e){
        return false;
      }
    }

    // Case 3: Only one threshold input provided
    try {
      if(thresholdMinText != null && thresholdMinText.isNotEmpty){
        double.parse(thresholdMinText);
      }
      if (thresholdMaxText != null && thresholdMaxText.isNotEmpty){
        double.parse(thresholdMaxText);
      }
      return true;
    } catch(e){
      return false;
    }
  }

  bool verify_zoom_inputs({String? zoomStartText, String? zoomEndText, double? startTime, double? endTime}){

    // Case 1: No zoom inputs - always valid
    if((zoomStartText == null || zoomStartText.isEmpty) && 
       (zoomEndText == null || zoomEndText.isEmpty)){
        return true;
       }

    // Case 2: Both zoom inputs provided
    if (zoomStartText != null && zoomStartText.isNotEmpty && zoomEndText != null && zoomEndText.isNotEmpty){
      try {
        double zoomStart = double.parse(zoomStartText);
        double zoomEnd = double.parse(zoomEndText);

        if (zoomStart >= zoomEnd){
          return false;
        }
        return true;
      } catch(e){
        return false;
      }
    }

    // Case 3: Only one zoom input provided
    try {
      if(zoomStartText != null && zoomStartText.isNotEmpty){
        double zoomStart = double.parse(zoomStartText);
        if(startTime != null && endTime != null){
          if(zoomStart<startTime || zoomStart>endTime){
            return false;
          }
        }
      }
      if (zoomEndText != null && zoomEndText.isNotEmpty){
        double zoomEnd= double.parse(zoomEndText);
        if(startTime != null && endTime != null){
          if(zoomEnd<startTime || zoomEnd>endTime){
            return false;
          }
        }
      }
      return true;
    } catch(e){
      return false;
    }
  }

  bool verify_limit_inputs({String? limiMinText, String? limitMaxText}){

    // Case 1: No limit inputs - always valid
    if((limiMinText == null || limiMinText.isEmpty) && 
       (limitMaxText == null || limitMaxText.isEmpty)){
        return true;
       }

    // Case 2: Both limit inputs provided
    if (limiMinText != null && limiMinText.isNotEmpty && limitMaxText != null && limitMaxText.isNotEmpty){
      try {
        double limitMin = double.parse(limiMinText);
        double limitMax = double.parse(limitMaxText);

        if (limitMin >= limitMax){
          return false;
        }
        return true;
      } catch(e){
        return false;
      }
    }

    // Case 3: Only one limit input provided
    try {
      if(limiMinText != null && limiMinText.isNotEmpty){
        double.parse(limiMinText);
      }
      if (limitMaxText != null && limitMaxText.isNotEmpty){
        double.parse(limitMaxText);
      }
      return true;
    } catch(e){
      return false;
    }

  }

  /*Fonction MOCAP*/

  Future<MotionData?> handle_analysis({
    required HolisticVideoResult? results, 
    required double startTime, 
    required double endTime,
    //required String frameRate, 
    required String bodyPart, 
    required String action, 
    bool isLateral=false
    }) async {

    if(!verify_start_and_end_inputs(startTime: startTime,endTime: endTime,videoDuration: results!.duration/1000.0)){
      return null;
    }

    MotionData? result;

    if(action == 'abdadd'){
      if(bodyPart == 'Head'){
        result = await analyze_head_abdadd(results,startTime,endTime);
      } else if (bodyPart == 'Shoulder'){
        result = await analyze_shoulder_abdadd(results,startTime,endTime);
      } else if(bodyPart == 'Torso'){
        result = await analyze_torso_abdadd(results,startTime,endTime);
      } else if(bodyPart == 'Arm'){
        result = await analyze_arm_abdadd(results,startTime,endTime);
      }
    } else if (action == 'flxext'){
      if(bodyPart == 'Head' && !isLateral){
        result = await analyze_head_flxext(results,startTime,endTime);
      } else if (bodyPart == 'Head' && isLateral){
        result = await analyze_head_lateral_flxext(results,startTime,endTime);
      } else if (bodyPart == 'Shoulder'){
        result = await analyze_shoulder_flxext(results,startTime,endTime);
      } else if (bodyPart == 'Torso'){
        result = await analyze_torso_flxext(results,startTime,endTime);
      } else if (bodyPart == 'Arm' && !isLateral){
        result = await analyze_arm_flxext(results,startTime,endTime);
      } else if (bodyPart == 'Arm' && isLateral){
        result = await analyze_arm_lateral_flxext(results,startTime,endTime);
      } else if (bodyPart == 'Fore Arm'){
        result = await analyze_forearm_flxext(results,startTime,endTime);
      }
    } else if (action == 'rotation'){
      if (bodyPart == 'Head'){
        result = await analyze_head_rotation(results,startTime,endTime);
      } else if (bodyPart == 'Torso'){
        result = await analyze_torso_rotation(results,startTime,endTime);
      }
    }

    if (result != null){
      currentMotionData = result;
    }

    return result;
  }

  Future<MotionData?> analyze_head_abdadd(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Abd_Add-head';
    return extractgraphs_ap_abd_add(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_head_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-head';
    return extractgraphs_ap_nodding(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_head_rotation(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Rot-head';
    return extractgraphs_ap_rotation(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_head_lateral_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-head_lat';
    return extractgraphs_ap_nodding_lat(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_shoulder_abdadd(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Abd_Add-shoulder';
    return extractgraphs_ap_abd_add_shoul(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_shoulder_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-shoulder';
    return extractgraphs_ap_shrugging(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_torso_abdadd(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Abd_Add-torso';
    return extractgraphs_ap_buste_abd_add(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_torso_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-torso';
    return extractgraphs_ap_buste_flexion(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_torso_rotation(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Rot-torso';
    return extractgraphs_ap_buste_rotation(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_arm_abdadd(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Abd_Add-arm';
    return extractgraphs_ap_arm_abduction(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_arm_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-arm';
    return extractgraphs_ap_arm_flexion(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_arm_lateral_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-arm_lat';
    return extractgraphs_ap_arm_flexion_lat(holisticResults: results, startTime: startTime, endTime: endTime);
  }

  Future<MotionData?> analyze_forearm_flxext(HolisticVideoResult? results,double startTime, double endTime)async{
    analysisName = 'Flx_Ext-forearm';
    return extractgraphs_ap_forearm_flexion(holisticResults: results, startTime: startTime, endTime: endTime);
  }
  
}

enum BodyPart { Head, Shoulder, Torso, Arm, Forearm }