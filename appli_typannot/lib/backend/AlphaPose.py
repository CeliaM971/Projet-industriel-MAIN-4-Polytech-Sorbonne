from Human_Coord import Human_Coord
import cv2

from abc import abstractmethod

class AlphaPose(Human_Coord): # AlphaPose a le marqueur "neck" en plus
    def __init__(self, texte,i):

        if type(i)==str: predictions = texte[i]["bodies"][0]["joints"]
        elif type(i)==int: predictions = texte[str(i)+'.jpg']["bodies"][0]["joints"]
            
        xnose,ynose,_,xneck,yneck,_,xright_shoulder,yright_shoulder,_,xright_elbow,yright_elbow,_,xright_wrist,yright_wrist,_,xleft_shoulder,yleft_shoulder,_,xleft_elbow,yleft_elbow,_,xleft_wrist,yleft_wrist,_,xright_hip,yright_hip,_,xright_knee,yright_knee,_,xright_ankle,yright_ankle,_,xleft_hip,yleft_hip,_,xleft_knee,yleft_knee,_,xleft_ankle,yleft_ankle,_,xleft_eyes,yleft_eyes,_,xright_eyes,yright_eyes,_,xleft_ear,yleft_ear,_,xright_ear,yright_ear,_ = predictions

        super().__init__(nose = [xnose,ynose],
                        left_eyes = [xleft_eyes,yleft_eyes],
                        right_eyes = [xright_eyes,yright_eyes],
                        left_ear = [xleft_ear, yleft_ear],
                        right_ear = [xright_ear, yright_ear],
                        left_shoulder = [xleft_shoulder,yleft_shoulder],
                        right_shoulder = [xright_shoulder,yright_shoulder],
                        left_elbow = [xleft_elbow,yleft_elbow],
                        right_elbow = [xright_elbow,yright_elbow],
                        left_wrist = [xleft_wrist,yleft_wrist],
                        right_wrist = [xright_wrist,yright_wrist],
                        left_hip = [xleft_hip,yleft_hip],
                        right_hip = [xright_hip,yright_hip],
                        left_knee = [xleft_knee,yleft_knee],
                        right_knee = [xright_knee,yright_knee],
                        left_ankle = [xleft_ankle,yleft_ankle],
                        right_ankle = [xright_ankle,yright_ankle])
        self.neck = [xneck,yneck]
    
    def get_neck(self):
        return tuple(int(n) for n in self.neck)
    
    @abstractmethod
    def draw_pose_on_image(self, image):

        cv2.line(image, tuple(self.get_nose()) , tuple(self.get_neck()) , (255,255,0), 3 ) # Nose - neck
        cv2.line(image, tuple(self.get_neck()) , tuple(self.get_midshoulder()) , (50,255,255), 3) # Neck - midshoulder
        super().draw_pose_on_image(image)
    
        return image
    