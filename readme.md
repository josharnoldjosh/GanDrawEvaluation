# Setting up the Teller Model
## Server.py
`server.py` has functions that are called from the javascript on the webpage.

### def message_recieved function
`def message_recieved` is where data from the drawer is sent after they send a message.

```python
@socketio.on('message')
def message_recieved(data):
    pass
```

* The `code` is the unique code for the task they are working on. Each task with have a unique code so multiple users can work on different tasks simultaneously without their data being mixed up.
* **user_txt** is the raw text that the Drawer has sent
* **seg_map** is the raw image data of the segmentation map. It must be converted in order to become an Image object.
* style is a string indicating which style is used.
 
```python
# Extract data
code = data["code"]
user_txt = data["text"]
seg_map = data["seg_map"]
style = data["style"]
```

In terms of the teller, the function, `TellerBot.speak(code)`  inside `message_recieved` is executed. You can go to `store.py` to modify the `TellerBot` class. `first_utterance()` should return a string of the first utterance from the Teller. Then, `speak()` should return subsequent utterances from the Teller. I already call `Store.save()` at the end of the `message_recieved` function to save the utterances and images, so you don’t need to worry about saving the utterances or the data. `synthetic_image` is returned from the `segmap_to_real` function which basically calls the NVIDIA API to convert our segmentation map to a synthetic image. To my understanding, the synthetic image is a string, see the next section to convert it.

## Note about images
The most of the images being passed around are strings, so to convert them to an image we must do:
```
from PIL import Image
import cv2
import numpy as np
import io
import base64

def stringToRGB(base64_string):
    imgdata = base64.b64decode(str(base64_string))
    image = Image.open(io.BytesIO(imgdata))
    return cv2.cvtColor(np.array(image), cv2.COLOR_BGR2RGB)
```

# Setting up the Drawer Model
```python
@socketio.on('teller_message')
def teller_message_recieved(data):
    pass
```

The above function is where information comes in from the teller.
*  `user_txt` is the raw text from the Teller
* `output_text = DrawerBot.speak(code)` generates the resultant text from the Drawer. You can modify the `DrawerBot` class in `store.py`. You could make this function return an image string too and pass it into the `Store.save()` function.

## Peeking
Lastly, the following function in `server.py` is called when the Teller wants to peek:
```python
@socketio.on('peek')
def peek(data):
    pass
```
You can modify the `Store.update_peek_image()` function to return the peek image, or, I could always do this too.

# Running on the server
If you want to run on the server, it’s important that `secure_connection_enabled` is set to true in `config.py`.
You should just need to run `gunicorn -k gevent -w 1 -b 127.0.0.1:1234 server:app;`. Also, in `templates/` folder, make sure to check both `index.html` and `teller.html`. Make sure that the line (~approximately line 20) for both `index.html` and `teller.html` are both:
```javascript
socket = io.connect('{{prefix}}://' + document.domain + ':' + location.port, {path: "/visualchatsocket”});
```
And not:
```javascript
socket = io.connect('{{prefix}}://' + document.domain + ':' + location.port);
```

If you want to run locally on your computer, make sure that in `templates/index.html` and `templates/teller.html` ~line 20 is:

```javascript
socket = io.connect('{{prefix}}://' + document.domain + ':' + location.port);
```

And also set `secure_connection_enabled` to false in `config.py`. Then run `python3 server.py` and visit `http://localhost:1234`. If you run into any errors trying to run this on the server, I need to make sure I am not running my version on the server. You can also kill all my tasks by doing:
```bash
killall -u jarnold
```
Or maybe my name is `jarnold9`:
```bash
killall -u jarnold9
```