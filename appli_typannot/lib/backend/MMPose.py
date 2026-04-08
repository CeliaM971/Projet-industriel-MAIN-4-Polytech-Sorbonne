import cv2
from abc import abstractmethod

from Human_Coord import Human_Coord

class MMPose(Human_Coord): # MMPose a les marqueurs ears en plus
    def __init__(self,texte,i): 

        if type(i)==int: predictions = texte[str(i)+'.json'][0]['keypoints']
        elif type(i)==str: predictions = texte[i][0]['keypoints']

        nose,left_eyes,right_eyes,left_ear,right_ear,left_shoulder,right_shoulder,left_elbow,right_elbow,left_wrist,right_wrist,left_hip,right_hip,left_knee,right_knee,left_ankle,right_ankle = predictions
        super().__init__(nose,
                        left_eyes,
                        right_eyes,
                        left_ear,
                        right_ear,
                        left_shoulder,
                        right_shoulder,
                        left_elbow,
                        right_elbow,
                        left_wrist,
                        right_wrist,
                        left_hip,
                        right_hip,
                        left_knee,
                        right_knee,
                        left_ankle,
                        right_ankle)
    
    @abstractmethod
    def draw_pose_on_image(self, image):

        cv2.line(image, tuple(self.get_nose()) , tuple(self.get_midshoulder()) , (75,255,75), 3 ) # Nose - midshoulder
        super().draw_pose_on_image(image)

        return image
