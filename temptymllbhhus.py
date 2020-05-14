imgByteArr = io.BytesIO()
    synthetic_image.save(imgByteArr, format='PNG')        
    synthetic_image = 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')    