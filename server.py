from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
from PIL import Image
import io
import base64
from api import segmap_to_real
from config import config
from time import sleep
import os
from Helper import *
from store import *

# Init the server
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, logger=True)

# Init the bots
print("Loading bots...")
cfg = get_cfg("/home/jarnold9/GanDraw/GeNeVA/example_args/gandraw_teller_args.json")
pretrained_model_path = "/home/jarnold9/GanDraw/GeNeVA/logs/teller"
teller_bot = TellerBot(cfg, pretrained_model_path)
print(teller_bot)

# cfg = get_cfg("/home/jarnold9/GanDraw/GeNeVA/example_args/gandraw_args.json")
# pretrained_model_path = "/home/jarnold9/GanDraw/GeNeVA/logs/drawer/silent"
# drawer_bot = DrawerBot(cfg, pretrained_model_path)
# print(drawer_bot)
print("Done")

@app.route('/')
def hello_world():    
    return os.getcwd()

"""
Human teller plays with drawer bot (talkative)
"""
@app.route('/talkative/drawer/<target_image>/<convo_id>/')
def talkative_drawer(convo_id, target_image):
    GameSelector.init_game(convo_id, user_type=UserType.talkative_drawer) 
    GameSelector.update_target_image(convo_id, target_image)   
    current_convo = Store.get_dialog(convo_id)
    synth, seg_map, peek_image = Store.target_image_data(convo_id)
    can_submit = GameSelector.can_submit(convo_id)
    token = ""
    if GameSelector.can_submit(convo_id): token = Store.token(convo_id) 
    prefix = 'http'
    if config['secure_connection_enabled']: prefix += 's'
    return render_template('teller.html', code=convo_id, synth=synth, seg_map=seg_map, dialog=current_convo, can_submit=can_submit, token=token, prefix=prefix, peek_image=peek_image, mode="talkative")

"""
Human teller plays with drawer bot (silent)
"""
@app.route('/silent/drawer/<target_image>/<convo_id>/')
def silent_drawer(convo_id, target_image):
    GameSelector.init_game(convo_id, user_type=UserType.silent_drawer)   
    GameSelector.update_target_image(convo_id, target_image)        
    current_convo = Store.get_dialog(convo_id)
    synth, seg_map, peek_image = Store.target_image_data(convo_id)
    can_submit = GameSelector.can_submit(convo_id)
    token = ""
    if GameSelector.can_submit(convo_id): token = Store.token(convo_id) 
    prefix = 'http'
    if config['secure_connection_enabled']: prefix += 's'
    return render_template('teller.html', code=convo_id, synth=synth, seg_map=seg_map, dialog=current_convo, can_submit=can_submit, token=token, prefix=prefix, peek_image=peek_image, mode="silent")

"""
Human drawer plays with teller bot (silent)
"""
@app.route('/silent/teller/<target_image>/<convo_id>/')
def silent_teller(convo_id, target_image):
    teller_bot.bot_mode = BotMode.silent
    GameSelector.init_game(convo_id, user_type=UserType.silent_teller)
    GameSelector.update_target_image(convo_id, target_image)   
    first_utt, _ = teller_bot.first_utterance(convo_id)    
    GameSelector.set_first_utt(convo_id, first_utt)
    current_convo = Store.get_dialog(convo_id)
    synth, seg_map, style = Store.current_image_data(convo_id)
    can_submit = GameSelector.can_submit(convo_id)
    token = ""
    if GameSelector.can_submit(convo_id): token = Store.token(convo_id) 
    prefix = 'http'
    if config['secure_connection_enabled']: prefix += 's'
    return render_template('index.html', code=convo_id, synth=synth, seg_map=seg_map, dialog=current_convo, style=style, can_submit=can_submit, token=token, prefix=prefix, mode="silent")    

"""
Human drawer plays with teller bot (talkative)
"""
@app.route('/talkative/teller/<target_image>/<convo_id>/')
def talkative_teller(convo_id, target_image):
    teller_bot.bot_mode = BotMode.talkative
    GameSelector.init_game(convo_id, user_type=UserType.talkative_teller)
    GameSelector.update_target_image(convo_id, target_image)   
    first_utt, _ = teller_bot.first_utterance(convo_id)    
    GameSelector.set_first_utt(convo_id, first_utt)
    current_convo = Store.get_dialog(convo_id)
    synth, seg_map, style = Store.current_image_data(convo_id)
    can_submit = GameSelector.can_submit(convo_id)
    token = ""
    if GameSelector.can_submit(convo_id): token = Store.token(convo_id) 
    prefix = 'http'
    if config['secure_connection_enabled']: prefix += 's'
    return render_template('index.html', code=convo_id, synth=synth, seg_map=seg_map, dialog=current_convo, style=style, can_submit=can_submit, token=token, prefix=prefix, mode="talkative")    


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
    mode = data["mode"]
    
    # Send data back
    token = ""
    if GameSelector.can_submit(code):
        token = Store.token(code) 

    synthetic_image, success = segmap_to_real(seg_map, style=style)    
    imgByteArr = io.BytesIO()
    synthetic_image.save(imgByteArr, format='PNG')        
    synthetic_image = 'data:image/png;base64,'+ base64.b64encode(imgByteArr.getvalue()).decode('ascii')    
    
    output_text = teller_bot.speak(synthetic_image, code, user_txt)

    emit("response", {"text":output_text, "synth":synthetic_image, "success":success, "token":token, "code":code})

    # Save our data
    Store.save(code, user_txt, output_text, seg_map, synthetic_image, style, success)

@socketio.on('teller_message')
def teller_message_recieved(data):
    """
    When the user sends data at each turn.
    """

    # print("teller message recieved handler called...?")

    # Extract data
    code = data["code"]
    user_txt = data["text"]
    mode = data["mode"]
    
    # Send data back
    token = ""
    if GameSelector.can_submit(code): token = Store.token(code) 

    if mode == "talkative":
        output_text = TalkativeDrawerBot.speak(code)
    else:
        output_text = SilentDrawerBot.speak(code)

    Store.save(code, user_txt, output_text)

    # Send response back
    emit("response", {"text":output_text, "token":token, "code":code})

@socketio.on('peek')
def peek(data):
    image, peeks_left = Store.update_peek_image(data['code'])
    emit("peek_response", {"code":data['code'], 'image':image, 'peeks_left':peeks_left})

@socketio.on('update_worker_id')
def update_worker_id(data):
    print(data)
    result = Store.load_data(data['code'])
    result['worker_id'] = data['worker_id']
    Store.save_data(data['code'], result)
    return

if __name__ == '__main__':
    """ Run the app. """    
    socketio.run(app, port=1234)