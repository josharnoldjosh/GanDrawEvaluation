import os
from PIL import Image
import base64
import io

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