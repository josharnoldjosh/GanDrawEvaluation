import os
from PIL import Image
import base64
import io
import json
import cv2
import numpy as np
import re

def path_to_bytes(path, intermediate="target_images"):
    path_to_try = f"{os.getcwd()}/{intermediate}/{path}"
    try:
        image = Image.open(path_to_try)
        imgByteArr = io.BytesIO()
        image.save(imgByteArr, format='PNG')        
        return 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')
    except:
        print(path_to_try)
        return ""
        
def byte_string_to_cv2(base64_string):            
    base64_string = re.sub('^data:image/.+;base64,', '', base64_string)    
    imgdata = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(imgdata))
    return cv2.cvtColor(np.array(image), cv2.COLOR_BGR2RGB)

def cv2_to_base64(image):
    try:
        # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(image)
        imgByteArr = io.BytesIO()
        image.save(imgByteArr, format='PNG')        
        return 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')
    except Exception as error:
        print("Uh oh! There was an error!", error)
        return ""

import easydict
def get_cfg(config_file):
    with open(config_file, 'r') as f:
        cfg = json.load(f)
    cfg = easydict.EasyDict(cfg)
    return cfg