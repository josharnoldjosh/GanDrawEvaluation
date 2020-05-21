from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
from PIL import Image
from store import Store, GameSelector, TellerBot, UserType, DrawerBot
import io
import base64
from api import segmap_to_real
from config import config
from time import sleep
import os

# Init the server
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, logger=True)

@app.route('/')
def hello_world():
    return os.getcwd()

@app.route('/teller/<convo_id>/')
def teller(convo_id):
    GameSelector.init_game(convo_id, user_type=UserType.teller)
    current_convo = Store.get_dialog(convo_id)
    synth, seg_map, peek_image = Store.target_image_data(convo_id)
    can_submit = GameSelector.can_submit(convo_id)
    token = ""
    if GameSelector.can_submit(convo_id): token = Store.token(convo_id) 
    prefix = 'http'
    if config['secure_connection_enabled']: prefix += 's'
    return render_template('teller.html', code=convo_id, synth=synth, seg_map=seg_map, dialog=current_convo, can_submit=can_submit, token=token, prefix=prefix, peek_image=peek_image)    

@app.route('/drawer/<convo_id>/')
def drawer(convo_id):
    GameSelector.init_game(convo_id, user_type=UserType.drawer)
    current_convo = Store.get_dialog(convo_id)
    synth, seg_map, style = Store.current_image_data(convo_id)
    can_submit = GameSelector.can_submit(convo_id)
    token = ""
    if GameSelector.can_submit(convo_id): token = Store.token(convo_id) 
    prefix = 'http'
    if config['secure_connection_enabled']: prefix += 's'
    return render_template('index.html', code=convo_id, synth=synth, seg_map=seg_map, dialog=current_convo, style=style, can_submit=can_submit, token=token, prefix=prefix)    

@socketio.on('change_style')
def change_style(data):
    seg_map = data["seg_map"]
    style = data["style"]
    synthetic_image, success = segmap_to_real(seg_map, style=style)
    imgByteArr = io.BytesIO()
    synthetic_image.save(imgByteArr, format='PNG')        
    synthetic_image = 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')    
    emit("style_response", {"synth":synthetic_image, "success":success, 'code':data['code']})
    Store.update_image(data["code"], seg_map, synthetic_image, style)

@socketio.on('message')
def message_recieved(data):
    """
    When the user sends data at each turn.
    """

    # Extract data
    code = data["code"]
    user_txt = data["text"]
    seg_map = data["seg_map"]
    style = data["style"]
    
    # Send data back
    token = ""
    if GameSelector.can_submit(code): token = Store.token(code) 
    output_text = TellerBot.speak(code)
    synthetic_image, success = segmap_to_real(seg_map, style=style)    
    imgByteArr = io.BytesIO()
    synthetic_image.save(imgByteArr, format='PNG')        
    synthetic_image = 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')    
    emit("response", {"text":output_text, "synth":synthetic_image, "success":success, "token":token, "code":code})

    # Save our data
    Store.save(code, user_txt, output_text, seg_map, synthetic_image, style, success)

@socketio.on('teller_message')
def teller_message_recieved(data):
    """
    When the user sends data at each turn.
    """

    # Extract data
    code = data["code"]
    user_txt = data["text"]
    
    # Send data back
    token = ""
    if GameSelector.can_submit(code): token = Store.token(code) 
    output_text = DrawerBot.speak(code)    
    Store.save(code, user_txt, output_text)

    # Give impression of drawing
    sleep(2)

    # Send response back
    emit("response", {"text":output_text, "token":token, "code":code})

@socketio.on('peek')
def peek(data):
    image, peeks_left = Store.update_peek_image(data['code'])
    emit("peek_response", {"code":data['code'], 'image':image, 'peeks_left':peeks_left})

if __name__ == '__main__':
    """ Run the app. """    
    socketio.run(app, port=1234)