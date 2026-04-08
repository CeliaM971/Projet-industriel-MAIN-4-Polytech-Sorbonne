import 'dart:math';
import 'constants.dart';
import 'mediapipe_service.dart';

double dist2point2D(double x1,double y1, double x2, double y2){
  return sqrt(pow(x1-x2,2) + pow(y1 - y2, 2));
}


double dist2points2D(List<double> A,List<double> B){
  return sqrt(pow(A[0] - B[0], 2) + pow(A[1] - B[1], 2));
}


double angle_between_points(List<double> p2, List<double> p1, List<double> p3){
  double dx1 = p1[0] - p2[0];
  double dy1 = p1[1] - p2[1];
  double dx2 = p3[0] - p2[0];
  double dy2 = p3[1] - p2[1];
  double angle1 = atan2(dy1,dx1);
  double angle2 = atan2(dy2,dx2);
  double angle = (angle2 - angle1) * (180/pi);
  if (angle<0) angle += 360;
  return angle;
}

double getAngle(List<double> a, List<double> b, List<double> c){
  List<double> vector_1 = [c[0] - a[0], c[1] - a[1]];
  List<double> vector_2 = [b[0] - a[0], b[1] - a[1]];

  double inner = vector_1[0] * vector_2[0] + vector_1[1] * vector_2[1];
  double norms = sqrt(vector_1[0] * vector_1[0] + vector_1[1] * vector_1[1]) * sqrt(vector_2[0] * vector_2[0] + vector_2[1] * vector_2[1]);

  if(norms.abs() < 1e-10){
    norms = 1e-10 * (norms > 0 ? 1 : -1);
  }
  double cos = inner/norms;
  double rad = acos(cos.clamp(-1.0,1.0));
  double deg = rad * (180/pi);

  return deg;
}


double getAngleVec(List<double> u, List<double> v){
  double norme_u = sqrt(u[0] * u[0] + u[1] * u[1]);
  double norme_v = sqrt(v[0] * v[0] + v[1] * v[1]);
  double normMului = norme_u * norme_v;
  double produit_scalaire = u[0] * v[0] + u[1] * v[1];

  if(normMului.abs()<1e-10){
    normMului = 1e-10 * (normMului > 0 ? 1 : -1);
  }

  double angle;
  if(produit_scalaire / normMului > 1){
    angle = acos(1);
  }
  else if(produit_scalaire / normMului < -1){
    angle = acos(-1);
  }
  else {
    angle = acos(produit_scalaire / normMului);
  }

  double deg = angle*(180/pi);
  return deg;
}

List<double> vecteurCord(List<double> point1, List<double> point2){
  return [point2[0] - point1[0], point2[1] - point1[1]];
}

double getAngleVecNega(List<double> vecteur1,List<double> vecteur2){
  double produit_scalaire = vecteur1[0] * vecteur2[0] + vecteur1[1] * vecteur2[1];
  double norme1 = sqrt(vecteur1[0] * vecteur1[0] + vecteur1[1] * vecteur1[1]);
  double norme2 = sqrt(vecteur2[0] * vecteur2[0] + vecteur2[1] * vecteur2[1]);

  double denominator = norme1*norme2;
  if(denominator.abs() < 1e-10){
    denominator = 1e-10 * (denominator > 0 ? 1 : -1);
  }

  double angle_radians;
  if(produit_scalaire/denominator > 1){
    angle_radians = acos(1);
  }
  else if(produit_scalaire/denominator < -1){
    angle_radians = acos(-1);
  }
  else{
    angle_radians = acos(produit_scalaire/denominator);
  }

  double angle_degres = angle_radians * (180/pi);
  double determinant = vecteur1[0] * vecteur2[1] - vecteur1[1] * vecteur2[0];
  
  if(determinant<0){
    angle_degres = -angle_degres;
  }

  return angle_degres;
}

List<double> filtreMoyenneur1D(List<double> data, int taille){
  if (taille % 2 == 0){
    taille += 1;
  }
  int demiTaille = taille ~/2;

  List<double> result = List.from(data);
  for (int i = demiTaille; i<data.length-demiTaille;i++){
    double sum = 0;
    for (int j = i-demiTaille; j<= i +demiTaille; j++){
      sum += data[j];
    }
    result[i] = sum/taille;
  }
  return result;
}

MotionData apply_limit_to_data(MotionData motion_data, double limit_min, double limit_max){
  List<double> clipped_values = motion_data.values.map((v) => v.clamp(limit_min,limit_max)).toList();
  List<double>? clipped_valuesLeft;
  if(motion_data.valuesLeft != null){
    clipped_valuesLeft = motion_data.valuesLeft!.map((v) => v.clamp(limit_min,limit_max)).toList();
  }

  return MotionData(times:motion_data.times,values: clipped_values,valuesLeft: clipped_valuesLeft,missingKeypoints: motion_data.missingKeypoints,
  );
}

bool has_bilateral_data(MotionType motionType){
  const bilateral_motion_types = [
    MotionType.SHOULDER_FLXEXT,
    MotionType.ARM_ABDADD,
    MotionType.ARM_FLXEXT,
    MotionType.ARM_FLXEXT_LAT,
    MotionType.FOREARM_FLXEXT,
  ];
  return bilateral_motion_types.contains(motionType);
}

/*FONCTIONS MOCAP*/

MotionData? extractgraphs_ap_abd_add({required HolisticVideoResult? holisticResults, required double startTime, required double endTime, }){

  List<double> angles = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for(var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    //Vérification qualité keypoints
    List<int> listToOk = [2, 5, 14, 15];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    //Récupération des keypoints nécessaires
    var Nose = frame.nose;
    var EyesD = frame.rightEye;
    var EyesG = frame.leftEye;
    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;

    //Calculs géométriques
    double denominator = EyesG.x - EyesD.x;
    if (denominator.abs() < 1e-10){
      denominator = 1e-10 * (denominator>= 0 ? 1 : -1);
    }
    double p_eyes = (EyesG.y - EyesD.y)/denominator;

    denominator = SholG.x - SholD.x;
    if (denominator.abs() < 1e-10){
      denominator = 1e-10 * (denominator >= 0 ? 1 : -1);
    }
    double p_shou = (SholG.y - SholD.y) / denominator;

    if (p_eyes.abs() < 1e-10){
      p_eyes = 1e-10 * (p_eyes >= 0 ? 1 : -1);
    }
    double p_per1 = -1 / p_eyes;

    double o1 = Nose.y - p_per1 * Nose.x;
    double o2 = SholD.y - p_shou * SholD.x;

    denominator = p_per1 - p_shou;
    if(denominator.abs() < 1e-10){
      denominator = 1e-10 * (denominator>= 0 ? 1 : -1);
    }
    double x = (o2-o1)/denominator;
    double y = p_shou * x + o2;

    if(p_shou.abs() < 1e-10){
      p_shou = 1e-10 * (p_shou>= 0 ? 1 : -1);
    }
    double p_per2 = -1/p_shou;

    denominator = (1-p_per2 * p_per1);
    if(denominator.abs() < 1e-10){
      denominator = 1e-10 * (denominator>= 0 ? 1 : -1);
    }
    double angle = -atan((p_per2 -p_per1)/denominator) * (180/pi);

    angles.add(angle);
    times.add(timeInSeconds);
  }

  if(angles.isEmpty) return null;

  angles = filtreMoyenneur1D(angles, 7);
  return MotionData(times: times, values: angles, missingKeypoints: errorIndices.toList(),);
}


MotionData? extractgraphs_ap_nodding({required HolisticVideoResult? holisticResults, required double startTime, required double endTime,}){
  List<double> distList = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    //Vérification qualité keypoints
    List<int> listToOk = [0,16,17];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    //Récupération des keypoints nécessaires
    var Nose = frame.nose;
    var EarG = frame.leftEar;
    var EarD = frame.rightEar;
    double mEar = (EarG.y + EarD.y)/2;

    distList.add(mEar - Nose.y);
    times.add(timeInSeconds);
  }

  if(distList.isEmpty) return null;

  distList = filtreMoyenneur1D(distList, 9);
  return MotionData(times: times, values: distList, missingKeypoints:errorIndices.toList(),);
}


MotionData? extractgraphs_ap_rotation({required HolisticVideoResult? holisticResults, required double startTime, required double endTime,}){
  List<double> angles = [];
  List<double> times = [];
  Set<int> errorIndices = {};
  Map<int,double> FactGtoD = {};

  double maxFact = 0;
  bool change = true;

  int frameIdx = 0;
  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 2, 5, 14, 15, 16, 17];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    List<double> MShol = frame.midShoulder;
    var EarG = frame.leftEar;
    var EarD = frame.rightEar;
    var Nose = frame.nose;
    
    double distEarNose = dist2point2D(EarG.x, EarG.y, Nose.x, Nose.y);

    if(change == true && maxFact < distEarNose){
      maxFact = distEarNose;
    }
    if(change == true && MShol[0]-5 <= EarG.x &&  EarG.x <= MShol[0] + 5){
      change = false;
      maxFact = distEarNose;
    }
    FactGtoD[frameIdx] = MShol[0] - Nose.x;
    times.add(timeInSeconds);
    frameIdx++;
  }

  if(FactGtoD.isEmpty) return null;

  List<double> F = [];
  double maxFactSafe = maxFact.abs() < 1e-10 ? 1e-10 * (maxFact >= 0 ? 1 : -1) : maxFact;

  for (int i in FactGtoD.keys){
    F.add(FactGtoD[i]! * 90 / maxFactSafe);
  } 

  List<double> RotDtoG = filtreMoyenneur1D(F, 7);

  return MotionData(times:times,values:RotDtoG,missingKeypoints: errorIndices.toList(),);
}


MotionData? extractgraphs_ap_shrugging({required HolisticVideoResult? holisticResults, required double startTime, required double endTime,int processingChunkCounter = 0}){
  List<double> gauche = [];
  List<double> droite = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 2, 5, 14, 15];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    gauche.add(SholG.y);
    droite.add(SholD.y);
    times.add(timeInSeconds);
  }

  if(gauche.isEmpty) return null;

  if(processingChunkCounter == 0){
    double maxG = gauche.reduce((a,b) => a > b ? a : b);
    double minG = gauche.reduce((a,b) => a < b ? a : b);
    double maxD = droite.reduce((a,b) => a > b ? a : b);
    double minD = droite.reduce((a,b) => a < b ? a : b);

    double denominatorG = maxG -minG;
    double denominatorD = maxD - minD;

    if(denominatorG.abs() < 1e-10){
      denominatorG = 1e-10 * (denominatorG >= 0 ? 1 : -1);
    }
    if(denominatorD.abs() < 1e-10){
      denominatorD = 1e-10 * (denominatorD >= 0 ? 1 : -1);
    }

    for (int i = 0; i< gauche.length; i++){
      gauche[i] = 1 - (gauche[i] - minG) / denominatorG;
      droite[i] = 1- (droite[i] -minD) / denominatorD;
    }
    gauche = filtreMoyenneur1D(gauche, 7);
    droite = filtreMoyenneur1D(droite, 7);
  }

  return MotionData(times:times, values: droite, valuesLeft: gauche, missingKeypoints: errorIndices.toList());

}


MotionData? extractgraphs_ap_abd_add_shoul({required HolisticVideoResult? holisticResults, required double startTime, required double endTime,int processingChunkCounter = 0}){
  
  List<double> dist = [];
  List<double> refDist = [];
  List<double> distList = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 2, 5];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var Nose = frame.nose;
    refDist.add(dist2point2D(SholD.x, SholD.y, Nose.x, Nose.y));
    dist.add(dist2point2D(SholD.x, SholD.y, SholG.x, SholG.y));
    times.add(timeInSeconds);
  }

  if (dist.isEmpty) return null;

  double maxRefDist = refDist.reduce((a,b) => a > b ? a : b);
  if(maxRefDist.abs() < 1e-10) maxRefDist = 1e-10 * (maxRefDist >= 0 ? 1 : -1);
  double maxDistRef = dist.reduce((a,b) => a > b ? a : b);

  for (int j = 0; j<dist.length; j++){
    if(refDist[j]/maxRefDist > 0.6){
      distList.add(dist[j]);
    } else {
      distList.add(maxDistRef);
    }
  }

  if(processingChunkCounter == 0){
    double maxDist = distList.reduce((a,b) => a > b ? a : b);
    double minDist = distList.reduce((a,b) => a < b ? a : b);
    double denominator = maxDist - minDist;
    if(denominator.abs() < 1e-10){
      denominator = 1e-10 * (denominator >= 0 ? 1 : -1);
    }

    for (int i = 0;i<distList.length;i++){
      distList[i] = (distList[i] - minDist) / denominator;
    }

    distList = filtreMoyenneur1D(distList, 17);
    return MotionData(times:times,values:distList,missingKeypoints: errorIndices.toList(),);
  }

  return MotionData(times: times, values: distList, missingKeypoints: errorIndices.toList(),);

}

MotionData? extractgraphs_ap_arm_abduction({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  
  List<double> anglesD = [];
  List<double> anglesG = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [2, 3, 5, 6];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var CouD = frame.rightElbow;
    var CouG = frame.leftElbow;
    var HipD = frame.rightHip;
    var HipG = frame.leftHip;

    double anglD = getAngle([SholD.x,SholD.y], [CouD.x,CouD.y], [HipD.x,HipD.y]) - (90 - getAngle([SholD.x,SholD.y], [SholG.x,SholG.y], [HipD.x,HipD.y]));
    double anglG = getAngle([SholG.x,SholG.y], [CouG.x,CouG.y], [HipG.x,HipG.y]) - (90 - getAngle([SholG.x,SholG.y], [SholD.x,SholD.y], [HipG.x,HipG.y]));

    anglesD.add(anglD);
    anglesG.add(anglG);
    times.add(timeInSeconds);
  }

    if(anglesD.isEmpty) return null;

    anglesD = filtreMoyenneur1D(anglesD, 5);
    anglesG = filtreMoyenneur1D(anglesG, 5);

    return MotionData(times:times,values:anglesD,valuesLeft: anglesG,missingKeypoints: errorIndices.toList());
  
}


MotionData? extractgraphs_ap_arm_flexion({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  List<double> anglesD = [];
  List<double> anglesG = [];
  List<double> times = [];
  Set<int> errorIndices = {};
  const double fact = 0.6;

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [2, 3, 5, 6];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var CouD = frame.rightElbow;
    var CouG = frame.leftElbow;

    double shoulder_distance = dist2point2D(SholG.x, SholG.y, SholD.x, SholD.y);
    if (shoulder_distance.abs() < 1e-10){
      shoulder_distance = 1e-10 * (shoulder_distance >= 0 ? 1 : -1);
    }

    double anglD;
    double angleBetweenD = angle_between_points([SholD.x,SholD.y], [SholG.x,SholG.y], [CouD.x,CouD.y]);
    double distCouD = dist2point2D(CouD.x, CouD.y, SholD.x, SholD.y);

    if((80 < angleBetweenD && angleBetweenD < 120) || 
       (220 < angleBetweenD && angleBetweenD < 260) ||
        distCouD / shoulder_distance < fact){
          if(CouD.y > SholD.y){
            anglD = 90 * (1 - distCouD / shoulder_distance);
          } else {
            anglD = 90 * (1 + distCouD / shoulder_distance);
          }
    } else {
      anglD = 0;
    }

    double anglG;
    double angleBetweenG = angle_between_points([SholG.x,SholG.y], [CouG.x,CouG.y], [SholD.x,SholD.y]);
    double distCouG = dist2point2D(SholG.x, SholG.y, CouG.x, CouG.y);

    if((80 < angleBetweenG && angleBetweenG < 120) || 
       (220 < angleBetweenG && angleBetweenG < 260) ||
        distCouG / shoulder_distance < fact){
          if(CouG.y > SholG.y){
            anglG = 90 * (1 - distCouG / shoulder_distance);
          } else {
            anglG = 90 * (1 + distCouG / shoulder_distance);
          }
    } else {
      anglG = 0;
    }

    anglesD.add(anglD>0?anglD:0);
    anglesG.add(anglG>0?anglG:0);
    times.add(timeInSeconds);
  }

  if(anglesD.isEmpty) return null;

  anglesD = filtreMoyenneur1D(anglesD, 7);
  anglesG = filtreMoyenneur1D(anglesG, 7);

  return MotionData(times:times,values:anglesD,valuesLeft: anglesG,missingKeypoints: errorIndices.toList());
}


MotionData? extractgraphs_ap_forearm_flexion({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  List<double> anglesD = [];
  List<double> anglesG = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [2, 3, 5, 6];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }
    
    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var CouD = frame.rightElbow;
    var CouG = frame.leftElbow;
    var PoigD = frame.rightWrist;
    var PoigG = frame.leftWrist;

    double anglG = getAngle([CouG.x,CouG.y], [PoigG.x,PoigG.y], [SholG.x,SholG.y]);
    double anglD = getAngle([CouD.x,CouD.y],  [SholD.x,SholD.y], [PoigD.x,PoigD.y]);
    
    double distCouPoigG = dist2point2D(CouG.x, CouG.y, PoigG.x, PoigG.y);
    double distCouSholG = dist2point2D(CouG.x, CouG.y, SholG.x, SholG.y);

    // Quand l'avant-bras fait une ligne droite en passant par l'avant du corps et non en faisant un tour sur le côté
    if(!(30<anglG && anglG < 300) || distCouPoigG < distCouSholG / 2){
      anglG += 180;
    }

    double distCouPoigD = dist2point2D(CouD.x, CouD.y, PoigD.x, PoigD.y);
    double distCouSholD = dist2point2D(CouD.x, CouD.y, SholD.x, SholD.y);

    if(!(30 < anglD && anglD < 300) || distCouPoigD < distCouSholD / 2){
      anglD += 180;
    }

    anglesD.add(anglD);
    anglesG.add(anglG);
    times.add(timeInSeconds);
  }

  if(anglesD.isEmpty) return null;

  anglesD = filtreMoyenneur1D(anglesD, 7);
  anglesG = filtreMoyenneur1D(anglesG, 7);

  return MotionData(times:times,values:anglesD,valuesLeft: anglesG,missingKeypoints: errorIndices.toList(),);
}


MotionData? extractgraphs_ap_buste_flexion({required HolisticVideoResult? holisticResults, required double startTime, required double endTime,int processingChunkCounter=0}){
  List<double> distNormT = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [2, 5, 8, 11];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var HipD = frame.rightHip;
    var HipG = frame.leftHip;

    double angle = getAngleVecNega(vecteurCord([SholD.x,SholD.y], [SholG.x,SholG.y]), vecteurCord([HipD.x,HipD.y], [HipG.x,HipG.y]));

    if(angle.abs()<15){
      distNormT.add(dist2points2D(frame.midShoulder, frame.midHip));
    }
    times.add(timeInSeconds);

  }
  
  if(distNormT.isEmpty) return null;

  if(processingChunkCounter == 0){
    double minDist = distNormT.reduce((a,b) => a < b ? a : b);
    double maxDist = distNormT.reduce((a,b) => a > b ? a : b);
    double denominator = maxDist - minDist;

    if(denominator.abs() < 1e-10) denominator = 1e-10 * (denominator >= 0 ? 1 :-1);

    for (int i = 0; i < distNormT.length; i++){
      distNormT[i] = (distNormT[i] - minDist) /denominator;
    }

    distNormT = filtreMoyenneur1D(distNormT, 5);
  }

  return MotionData(times:times,values:distNormT,missingKeypoints: errorIndices.toList());
}


MotionData? extractgraphs_ap_buste_abd_add({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  List<double> angles = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 2, 5, 8, 11];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var HipD = frame.rightHip;
    var HipG = frame.leftHip;

    double angle = getAngleVecNega(vecteurCord([SholD.x,SholD.y], [SholG.x,SholG.y]), vecteurCord([HipD.x,HipD.y], [HipG.x,HipG.y]));

    angles.add(angle);
    times.add(timeInSeconds);
  }

  if(angles.isEmpty) return null;

  angles = filtreMoyenneur1D(angles, 11);

  return MotionData(times: times, values: angles,missingKeypoints: errorIndices.toList());
}


MotionData? extractgraphs_ap_buste_rotation({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  List<double> angles = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 2, 5, 8, 11];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var HipD = frame.rightHip;
    var HipG = frame.leftHip;
    var Nose = frame.nose;

    double denominator = dist2point2D(HipD.x, HipD.y, HipG.x, HipG.y);
    if(denominator.abs() < 1e-10){
      denominator = 1e-10 * (denominator >= 0 ? 1 : -1);
    }

    double fact = dist2point2D(HipD.x, HipD.y, HipG.x, HipG.y)/denominator; //Pour savoir si il est de profil ou de face
    double maxFact = 1.7;

    if((HipG.x - Nose.x).abs() > (Nose.x - HipD.x).abs()){
      angles.add(90*(maxFact-fact)+10);
    }
    else if((HipG.x - Nose.x - (Nose.x - HipD.x)).abs() < 10){
      angles.add(0);
    }
    else {
      angles.add(90*(fact - maxFact) + 10);
    }

    times.add(timeInSeconds);

  }

  if(angles.isEmpty) return null;

  angles = filtreMoyenneur1D(angles, 11);

  return MotionData(times:times, values: angles, missingKeypoints: errorIndices.toList());

}


MotionData? extractgraphs_ap_lat_nod({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  List<double> angles = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 16, 17];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var Nose = frame.nose;
    var EarG = frame.leftEar;
    var EarD = frame.rightEar;
    double MEar = (EarG.y + EarD.y)/2;

    if(MEar-10 <= Nose.y && Nose.y <= MEar + 10){
      angles.add(0);
    } else {
      angles.add(MEar - Nose.y);
    }

    times.add(timeInSeconds);
  }
  if(angles.isEmpty) return null;

  angles = filtreMoyenneur1D(angles, 5);

  return MotionData(times:times, values:angles, missingKeypoints: errorIndices.toList());
}


MotionData? extractgraphs_ap_arm_flexion_lat({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){
  List<double> anglesD = [];
  List<double> anglesG = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 2, 3, 5, 6];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var SholD = frame.rightShoulder;
    var SholG = frame.leftShoulder;
    var CouD = frame.rightElbow;
    var CouG = frame.leftElbow;
    var Nose = frame.nose;

    List<double> point0 = [0,0];
    List<double> point1 = [0,1];

    double anglD;
    double anglG;
    
    double distShouNose = dist2point2D(SholD.x, SholD.y, SholG.x, SholG.y);
    double distSholNose = dist2point2D(SholD.x, SholD.y, Nose.x, Nose.y);

    if(distShouNose < distSholNose){
      double midSholX = (SholD.x + SholG.x)/2;

      if(midSholX > Nose.x){
        anglD = -getAngleVecNega(vecteurCord([SholD.x,SholD.y], [CouD.x,CouD.y]), vecteurCord(point0, point1));
        anglG = -getAngleVecNega(vecteurCord([SholG.x,SholG.y], [CouG.x,CouG.y]), vecteurCord(point0, point1));
      }
      else {
        anglD = getAngleVecNega(vecteurCord([SholD.x,SholD.y], [CouD.x,CouD.y]), vecteurCord(point0, point1));
        anglG = getAngleVecNega(vecteurCord([SholG.x,SholG.y], [CouG.x,CouG.y]), vecteurCord(point0, point1));
      }
    } else {
      anglD = 0;
      anglG = 0;
    }

    if(SholD.y > CouD.y && anglD < 0) anglD = 360 + anglD;
    if(SholG.y > CouG.y && anglG < 0) anglG = 360 + anglG;

    anglesD.add(anglD);
    anglesG.add(anglG);
    times.add(timeInSeconds);
  }

  if(anglesD.isEmpty) return null;

  anglesD = filtreMoyenneur1D(anglesD, 7);
  anglesG = filtreMoyenneur1D(anglesG, 7);

  return MotionData(times:times, values:anglesD,valuesLeft: anglesG, missingKeypoints: errorIndices.toList());
}



MotionData? extractgraphs_ap_nodding_lat({required HolisticVideoResult? holisticResults, required double startTime, required double endTime}){

  List<double> distList = [];
  List<double> times = [];
  Set<int> errorIndices = {};

  for (var frameData in holisticResults!.frames){
    double timeInSeconds = frameData.timestamp/1000.0;

    if(timeInSeconds < startTime || timeInSeconds > endTime) continue;

    var frame  = frameData.keypoints;

    List<int> listToOk = [0, 3, 4];
    for (int index in listToOk){
      if(index>=frame.pose.length){
        errorIndices.add(index);
        continue;
      }
      var landmark = frame.pose[index];
      if(landmark.visibility != null && landmark.visibility! < 0.2){
        errorIndices.add(index);
      }
    }

    var Nose = frame.nose;
    var EarG = frame.leftEar;
    var EarD = frame.rightEar;
    double MEarX = (EarG.x+EarD.x)/2;
    double MEarY = (EarG.y+EarD.y)/2;
    List<double> MHip = frame.midHip;
    List<double> MSho = frame.midShoulder;
    distList.add(getAngleVec(vecteurCord(MHip, MSho), vecteurCord([Nose.x,Nose.y], [MEarX,MEarY])));
    times.add(timeInSeconds);
  }

  distList = filtreMoyenneur1D(distList, 9);
  return MotionData(times:times, values:distList, missingKeypoints: errorIndices.toList());
}
