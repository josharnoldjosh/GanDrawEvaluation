import os
import json
import base64
from random import choice
from uuid import uuid4
from enum import Enum
from PIL import Image
from random import choice
import io
from Helper import *

"""
I've done this a bit weird, where I generate the first response of the Teller, then I store data as
Turn:
    - User response
    - Teller response

When really its like

Turn:
    - Teller response
    - User response

But this is so the socket io & networking is easier, so when I post process this data it might make sense to offset everything.
This should be super easy since each image of the turn is literally bundled in the json data.
"""

class UserType(Enum):
    silent_drawer=0
    silent_teller=1
    talkative_drawer=2
    talkative_teller=3

class SilentTellerBot:
    
    @classmethod
    def first_utterance(cls, data):
        return "There is a mountain in the background"

    @classmethod
    def speak(cls, image, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        turns = ["There is some grass in the foreground", "Add a small pond in the middle", "add some trees in the background", "its currently sunset at the moment"]
        try:
            return turns[num_turns]
        except:
            return "okay, I think we're done"

class TalkativeTellerBot:
    
    @classmethod
    def first_utterance(cls, data):
        return "There is a mountain in the background"

    @classmethod
    def speak(cls, image, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        turns = ["There is some grass in the foreground", "Add a small pond in the middle", "add some trees in the background", "its currently sunset at the moment"]
        try:
            return turns[num_turns]
        except:
            return "okay, I think we're done"            

class SilentDrawerBot:
    @classmethod
    def speak(cls, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        turns = ["Okay, next instruction please.", "I just drew it. What's next?"]
        try:
            return turns[num_turns]
        except:
            return "okay, I think we're done"

    @classmethod
    def peek(cls, convo_id):
        return
        # return the peek image...?

class TalkativeDrawerBot:
    @classmethod
    def speak(cls, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        turns = ["Okay, next instruction please.", "I just drew it. What's next?"]
        try:
            return turns[num_turns]
        except:
            return "okay, I think we're done"          

    @classmethod
    def peek(cls, convo_id):
        return
        # return the peek image...?


class GameSelector:
    
    @classmethod
    def target_image(cls):
        path = os.path.join(os.getcwd(), "target_images/")
        synth = choice([x for x in os.listdir(path) if ".jpg" in x])
        real = synth.replace(".jpg", ".png")
        return synth, real

    @classmethod
    def init_game(cls, convo_id, user_type):       
        if GameSelector.game_exists(convo_id): return 
        data = Store.load_data(convo_id)
        data['user_type'] = user_type.value
        if user_type == UserType.talkative_drawer:
            data['first_bot_utt'] = TalkativeTellerBot.first_utterance(data)
        elif user_type == UserType.silent_drawer:
            data['first_bot_utt'] = SilentTellerBot.first_utterance(data)
        Store.save_data(convo_id, data)

    @classmethod
    def game_exists(cls, convo_id):
        return os.path.exists(os.path.join(os.getcwd(), "saved_data/", f"{convo_id}.json"))

    @classmethod
    def can_submit(cls, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        if data['user_type'] == UserType.silent_teller.value or data['user_type'] == UserType.talkative_teller.value:
            return num_turns >= 2
        return num_turns >= 4

    @classmethod
    def token(cls):
        return str(uuid4())[:8]

class Store:

    @classmethod
    def preprocess_string(cls, x):
        return x.replace("'", "").lower()

    @classmethod
    def save(cls, convo_id, user_utt, bot_utt, seg_map=None, synth=None, style=None, success=None):
        """
        If it fails, we save the seg map but use the synth from previous image
        We tag this turn as failed, so we know to update the synth from the seg map
        """
        data = Store.load_data(convo_id)
        if not seg_map or not synth or not style:
            data["dialog"].append({"user":Store.preprocess_string(user_utt), "bot":Store.preprocess_string(bot_utt)})            
        else:    
            if not success: synth = data['dialog'][-1]['synth']            
            data["dialog"].append({"user":Store.preprocess_string(user_utt), "bot":Store.preprocess_string(bot_utt), "seg_map":seg_map, "synth":synth, "style":style, "success":success})            
        Store.save_data(convo_id, data)

    @classmethod
    def target_image_data(cls, convo_id):
        data = Store.load_data(convo_id)        
        return path_to_bytes(data['target_image']['synth']), path_to_bytes(data['target_image']['seg_map']), path_to_bytes(data['target_image']["most_recent_peek_image"], 'image_data')

    @classmethod
    def load_data(cls, convo_id):
        target_synth, target_seg = GameSelector.target_image()
        data = {"convo_id":convo_id, "dialog":[], "target_image":{"synth":target_synth, "seg_map":target_seg, "most_recent_peek_image":""}, "first_bot_utt":"", "token":GameSelector.token(), "num_peeks_left":2}                
        if not GameSelector.game_exists(convo_id): return data
        with open(os.path.join(os.getcwd(), "saved_data/", f"{convo_id}.json"), 'r') as file: data = json.load(file)
        return data
        
    @classmethod
    def save_data(cls, convo_id, data):
        with open(os.path.join(os.getcwd(), "saved_data/", f"{convo_id}.json"), 'w') as file:
            json.dump(data, file, indent=4)

    @classmethod
    def update_image(cls, convo_id, seg_map, synth, style):
        try:
            data = Store.load_data(convo_id)
            convo = data['dialog'][-1]
            convo['seg_map'] = seg_map
            convo['synth'] = synth
            convo['style'] = style
            Store.save_data(convo_id, data)
        except Exception as error:
            pass

    @classmethod
    def get_dialog(cls, convo_id):
        data = Store.load_data(convo_id)
        other_user = "Teller"
        if data['user_type'] == UserType.talkative_teller.value or data['user_type'] == UserType.silent_teller.value:
            other_user = "Drawer"
        text = f"{data['first_bot_utt']}\n\n" + "\n\n".join([f"You: {x['user']}\n\n{other_user}: {x['bot']}" for x in data["dialog"]]) + "\n\n"
        return text.strip()+"\n\n"

    @classmethod
    def get_image_data(cls, convo_id):
        data = Store.load_data(convo_id)
        return [turn['synth'] for turn in data['dialog']]
            
    @classmethod
    def current_image_data(cls, convo_id):
        data = Store.load_data(convo_id)
        try:
            last_convo = data['dialog'][-1]
            synth = last_convo['synth']
            seg_map = last_convo['seg_map']
            style = last_convo['style']
        except:
            synth = ""
            seg_map = ""
            style = "1"
        return synth, seg_map, style

    @classmethod
    def token(cls, convo_id):
        return Store.load_data(convo_id)['token']

    @classmethod
    def update_peek_image(cls, convo_id):        
        data = Store.load_data(convo_id)
        if data['num_peeks_left'] == 0: return path_to_bytes(data['target_image']['most_recent_peek_image'], 'image_data'), data['num_peeks_left']
        data['target_image']['most_recent_peek_image'] = choice([x for x in os.listdir("./image_data/") if ".jpg" in x])
        data['num_peeks_left'] = data['num_peeks_left'] - 1
        Store.save_data(convo_id, data)
        return path_to_bytes(data['target_image']['most_recent_peek_image'], 'image_data'), data['num_peeks_left']

    @classmethod
    def user_type(cls, convo_id):
        data = Store.load_data(convo_id)
        return data['user_type']