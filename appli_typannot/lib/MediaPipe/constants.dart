
enum PoseModel{
  mediaPipe(0),
  alphaPose(1),
  mmPose(2);

  final int value;
  const PoseModel(this.value);
}

enum MotionType{
  HEAD_ABDADD(11),
  HEAD_FLXEXT(12),
  HEAD_ROTATION(13),
  HEAD_ROT_LAT(14),
  SHOULDER_ABDADD(21),
  SHOULDER_FLXEXT(22),
  TORSO_ABDADD(31),
  TORSO_FLXEXT(32),
  TORSO_ROTATION(33),
  ARM_ABDADD(41),
  ARM_FLXEXT(42),
  ARM_FLXEXT_LAT(43),
  FOREARM_FLXEXT(51);

  final int value;
  const MotionType(this.value);
}