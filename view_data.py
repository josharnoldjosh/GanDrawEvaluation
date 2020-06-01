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
HTTP = 'http'
data = [x.split('.json')[0] for x in os.listdir('./saved_data/') if ".json" in x]
current_convo_id = [""]

def next_id():
    if current_convo_id != []:
        data.append(current_convo_id[0])
    convo_id = data.pop(0)    
    current_convo_id[0] = convo_id
    return convo_id

def prev_id():  
    if current_convo_id != []:  
        data.insert(0, current_convo_id[0])
    last = data[-1]
    data.pop(-1)    
    current_convo_id[0] = last
    return last

def id_to_data(convo_id):    
    user = Store.user_type(convo_id)
    if user == UserType.silent_teller.value or user == UserType.talkative_teller.value:
        pay_load = {'user_type':'drawer'}
        pay_load['dialog'] = Store.get_dialog(convo_id).replace("\n", "<br>")
        pay_load['image_data'] = Store.get_image_data(convo_id)
        return pay_load        
    elif user == UserType.silent_drawer.value or user == UserType.talkative_drawer.value:
        pay_load = {'user_type':'teller'}
        pay_load['dialog'] = Store.get_dialog(convo_id).replace("\n", "<br>")          
        return pay_load
    return {}

@app.route('/')
def root():
    return render_template('view_data.html', prefix=HTTP)

@socketio.on('next')
def next(data):
    emit("data", id_to_data(next_id()))
    
@socketio.on('prev')
def prev(data):
    emit("data", id_to_data(prev_id()))

if __name__ == '__main__':
    """ Run the app. """    
    socketio.run(app, port=3000)