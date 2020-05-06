import os
import json
import base64
from random import choice
from uuid import uuid4

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

class TellerBot:

    @classmethod
    def first_utterance(cls, data):
        return "There is a mountain in the background"

    @classmethod
    def speak(cls, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        turns = ["There is some grass in the foreground", "Add a small pond in the middle", "add some trees in the background", "its currently sunset at the moment"]
        try:
            return turns[num_turns]
        except:
            return "okay, I think we're done"

class GameSelector:

    @classmethod
    def target_image(cls):
        path = os.path.join(os.getcwd(), "target_images/")
        synth = choice([x for x in os.listdir(path) if ".jpg" in x])
        real = synth.replace(".jpg", ".png")
        return synth, real

    @classmethod
    def init_game(cls, convo_id):       
        if GameSelector.game_exists(convo_id): return 
        data = Store.load_data(convo_id)
        data['first_bot_utt'] = TellerBot.first_utterance(data)
        Store.save_data(convo_id, data)

    @classmethod
    def game_exists(cls, convo_id):
        return os.path.exists(os.path.join(os.getcwd(), "saved_data/", f"{convo_id}.json"))

    @classmethod
    def can_submit(cls, convo_id):
        data = Store.load_data(convo_id)
        num_turns = len(data['dialog'])
        return num_turns >= 4

    @classmethod
    def token(cls):
        return str(uuid4())[:8]

class Store:

    @classmethod
    def preprocess_string(cls, x):
        return x.replace("'", "").lower()

    @classmethod
    def save(cls, convo_id, user_utt, bot_utt, seg_map, synth, style, success):
        """
        If it fails, we save the seg map but use the synth from previous image
        We tag this turn as failed, so we know to update the synth from the seg map
        """
        data = Store.load_data(convo_id)
        if not success: synth = data['dialog'][-1]['synth']            
        data["dialog"].append({"user":Store.preprocess_string(user_utt), "bot":Store.preprocess_string(bot_utt), "seg_map":seg_map, "synth":synth, "style":style, "success":success})            
        Store.save_data(convo_id, data)

    @classmethod
    def target_image_data(cls, convo_id):
        data = Store.load_data(convo_id)
        return data['target_image']['synth'], data['target_image']['seg_map']

    @classmethod
    def load_data(cls, convo_id):
        target_synth, target_seg = GameSelector.target_image()
        data = {"convo_id":convo_id, "dialog":[], "target_image":{"synth":target_synth, "seg_map":target_seg}, "first_bot_utt":"", "token":GameSelector.token()}                
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
        text = f"{data['first_bot_utt']}\n\n" + "\n\n".join([f"You: {x['user']}\n\nTeller: {x['bot']}" for x in data["dialog"]]) + "\n\n"
        return text.strip()+"\n\n"

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