import cv2
import numpy as np
from abc import abstractmethod

class Human_Coord(): # Contient tout les marqueurs communs des deux modèles (AlphaPose et MMPose)

    def __init__(self,
                nose,
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
                right_ankle):
        
        self.nose = nose
        self.left_eyes = left_eyes
        self.right_eyes = right_eyes
        self.left_ear = left_ear
        self.right_ear = right_ear
        self.left_shoulder = left_shoulder
        self.right_shoulder = right_shoulder
        self.mid_shoulder = [(self.left_shoulder[0]+self.right_shoulder[0])/2, (self.left_shoulder[1]+self.right_shoulder[1])/2]
        self.left_elbow = left_elbow
        self.right_elbow = right_elbow
        self.left_wrist = left_wrist
        self.right_wrist = right_wrist
        self.left_hip = left_hip
        self.right_hip = right_hip
        self.mid_hip = [(self.left_hip[0]+self.right_hip[0])/2, (self.left_hip[1]+self.right_hip[1])/2]
        self.left_knee = left_knee
        self.right_knee = right_knee
        self.left_ankle = left_ankle
        self.right_ankle = right_ankle
    
    @abstractmethod
    def get_nose(self):
        return tuple(int(i) for i in self.nose)

    @abstractmethod
    def get_left_eyes(self):
        return tuple(int(i) for i in self.left_eyes)
    
    @abstractmethod
    def get_right_eyes(self):
        return tuple(int(i) for i in self.right_eyes)
    
    @abstractmethod
    def get_left_ear(self):
        return tuple(int(i) for i in self.left_ear)
    
    @abstractmethod
    def get_right_ear(self):
        return tuple(int(i) for i in self.right_ear)

    @abstractmethod
    def get_left_shoulder(self):
        return tuple(int(i) for i in self.left_shoulder)
    
    @abstractmethod
    def get_right_shoulder(self):
        return tuple(int(i) for i in self.right_shoulder)

    @abstractmethod
    def get_left_elbow(self):
        return tuple(int(i) for i in self.left_elbow)
    
    @abstractmethod
    def get_right_elbow(self):
        return tuple(int(i) for i in self.right_elbow)

    @abstractmethod
    def get_left_wrist(self):
        return tuple(int(i) for i in self.left_wrist)
    
    @abstractmethod
    def get_right_wrist(self):
        return tuple(int(i) for i in self.right_wrist)
    
    @abstractmethod
    def get_left_hip(self):
        return tuple(int(i) for i in self.left_hip)
    
    @abstractmethod
    def get_right_hip(self):
        return tuple(int(i) for i in self.right_hip)
    
    @abstractmethod
    def get_left_knee(self):
        return tuple(int(i) for i in self.left_knee)
    
    @abstractmethod
    def get_right_knee(self):
        return tuple(int(i) for i in self.right_knee)
    
    @abstractmethod
    def get_left_ankle(self):
        return tuple(int(i) for i in self.left_ankle)
    
    @abstractmethod
    def get_right_ankle(self):
        return tuple(int(i) for i in self.right_ankle)
    
    @abstractmethod
    def get_midshoulder(self):
        return tuple(int(i) for i in self.mid_shoulder)
    
    @abstractmethod
    def get_midhip(self):
        return tuple(int(i) for i in self.mid_hip)
    
    @abstractmethod
    def draw_pose_on_image(self, image):

        cv2.line(image, tuple(self.get_midshoulder()) , tuple(self.get_left_shoulder()) , (255,75,75), 3) # Midshoulder - leftshoulder
        cv2.line(image, tuple(self.get_midshoulder()) , tuple(self.get_right_shoulder()) , (255,75,75), 3) # Midshoulder - rightshoulder
        cv2.line(image, tuple(self.get_left_shoulder()) , tuple(self.get_left_elbow()) , (255,150,150), 3) # Leftshoulder - leftelbow
        cv2.line(image, tuple(self.get_left_elbow()) , tuple(self.get_left_wrist()) , (255,200,200), 3) # Leftelbow - leftwrist
        cv2.line(image, tuple(self.get_right_shoulder()) , tuple(self.get_right_elbow()) , (255,150,150), 3) # Rightshoulder -rightelbow
        cv2.line(image, tuple(self.get_right_elbow()) , tuple(self.get_right_wrist()) , (255,200,200), 3) # Rightelbow - rightwrist
        cv2.line(image, tuple(self.get_midshoulder()) , tuple(self.get_midhip()) , (255,255,255), 3) # Midshoulder - midhip
        cv2.line(image, tuple(self.get_midhip()) , tuple(self.get_left_hip()) , (150,150,255), 3) # Midhip - lefthip
        cv2.line(image, tuple(self.get_midhip()) , tuple(self.get_right_hip()) , (150,150,255), 3) # Midhip - righthip
        cv2.line(image, tuple(self.get_left_hip()) , tuple(self.get_left_knee()) , (75,75,255), 3) # Lefthip - leftknee
        cv2.line(image, tuple(self.get_left_knee()) , tuple(self.get_left_ankle()) , (0,0,255), 3) # Leftknee - leftankle
        cv2.line(image, tuple(self.get_right_hip()) , tuple(self.get_right_knee()) , (75,75,255), 3) # Rightthip - rightknee
        cv2.line(image, tuple(self.get_right_knee()) , tuple(self.get_right_ankle()) , (0,0,255), 3) # Rightknee - rightankle
        cv2.line(image, tuple(self.get_nose()) , tuple(self.get_right_eyes()) , (0,255,0), 3) # Nose - right eye
        cv2.line(image, tuple(self.get_nose()) , tuple(self.get_left_eyes()) , (0,255,0), 3) # Nose - left eye
