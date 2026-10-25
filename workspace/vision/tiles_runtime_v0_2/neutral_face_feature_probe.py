"""Offline development feature; not connected to Runtime or calibrated confidence.

Apply identically to query and reference images. The neutral bright-face mask
excludes saturated Ting badges before taking the dominant face rectangle.
"""
import cv2
import numpy as np
from workspace.vision.tiles_v0_1.template_classifier import _feature
def neutral(im):
 rgb=np.asarray(im.convert('RGB'));hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV);mask=((hsv[:,:,1]<80)&(hsv[:,:,2]>150)).astype(np.uint8)*255
 mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8));n,_,stats,_=cv2.connectedComponentsWithStats(mask,8)
 if n<=1:return _feature(im).astype(np.float32)
 x,y,w,h,area=stats[1:][np.argmax(stats[1:,4])]
 if area<rgb.shape[0]*rgb.shape[1]*.25 or w<8 or h<12:return feature(im,'gray')
 gray=cv2.cvtColor(cv2.resize(rgb[y:y+h,x:x+w],(48,72)),cv2.COLOR_RGB2GRAY)
 return cv2.equalizeHist(gray).astype(np.float32)
