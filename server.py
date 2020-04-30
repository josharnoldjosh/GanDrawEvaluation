from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
from PIL import Image
from store import Store
import io
import base64

# Init the server
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, logger=True)

@app.route('/')
def root():
    """ Send HTML from the server."""
    return render_template('index.html')

@socketio.on('message')
def message_recieved(data):
    """
    When the user sends data at each turn.
    """

    # The user's utterance at this turn
    user_txt = data["text"]

    # The user's segmentation map at this turn
    seg_map = data["seg_map"]
    image_data = base64.b64decode(seg_map.replace('data:image/png;base64,', ''))
    image = Image.open(io.BytesIO(image_data))

    # Get request
    urls = ['http://54.191.227.231:443/', 'http://34.221.84.127:443/', 'http://34.216.59.35:443/']


    # Update image and output text
    synthetic_image = image
    output_text = "Hello world"

    # Convert back to Base64 str
    imgByteArr = io.BytesIO()
    synthetic_image.save(imgByteArr, format='PNG')        
    synthetic_image = 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')    

    # Function to send to the front end html
    emit("response", {"text":output_text, "synth":synthetic_image})

    # Save our data
    Store.save("unique_id_here", user_txt, output_text, seg_map, synthetic_image)

if __name__ == '__main__':
    """ Run the app. """    
    socketio.run(app, port=2001)
    # socketio.run(app, port=2000)

"""
ToDo:
- target image selection?
- Setup a unique id, maybe generate one and assign to a session?
    - on completion, delete the session so when we revisit the page its new game
- save conversations
- automatically load conversations & images on page refresh?
- test running with gunicorn
- can get this link working on language, then can use an external link for mturk
"""