import sys
sys.path.insert(1, '/home/jarnold9/GanDraw/GeNeVA')

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

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm
import json  # Added to initialize the setting in Jupyter Notebook-by Mingyang
import easydict  # Added to initialize the setting in Jupyter Notebook-by Mingyang
import random
import numpy as np
import nltk
import string
from PIL import Image
from pathlib import Path
import cv2
import glob

from geneva.models.models import INFERENCE_MODELS
from geneva.data.datasets import DATASETS
from geneva.evaluation.evaluate import Evaluator
from geneva.utils.config import keys, parse_config
from geneva.utils.visualize import VisdomPlotter
from geneva.models.models import MODELS
from geneva.data import codraw_dataset
from geneva.data import clevr_dataset
from geneva.data import gandraw_dataset
from geneva.evaluation.seg_scene_similarity_score import report_gandraw_eval_result
from geneva.utils.config import keys
from math import sqrt

import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence
from torchvision import transforms
from teller_utils import UnNormalize

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

class ModelMode(Enum):
    talkative=0
    silent=1    

class TellerBot():
    def __init__(self, cfg, pretrained_model_path=None, iteration=6000):
        self.cfg = cfg
        self.cfg.batch_size = 1
        self.mode = ModelMode.talkative

        # Load the Dataset
        dataset_path = cfg.test_dataset
        gandraw_vocab_path = "/home/jarnold9/GanDraw/data/teller/gandraw_vocab.txt"
        with open(gandraw_vocab_path, 'r') as f:
            gandraw_vocab = f.readlines()
            gandraw_vocab = [x.strip().rsplit(' ', 1)[0] for x in gandraw_vocab]        
        self.vocab = ['<s_start>', '<s_end>', '<unk>', '<pad>', '<d_end>'] + gandraw_vocab        
        self.cfg.vocab_size = len(self.vocab)
        self.model = INFERENCE_MODELS[cfg.gan_type](cfg)

        # Load the pretrained_model
        if pretrained_model_path is not None:
            self.model.load_model('/'.join([pretrained_model_path,'snapshot_{}.pth'.format(iteration)]))
            
        self.iterations = cfg.batch_size # cfg.batch_size
        self.current_iteration=iteration
        #define the collate_fn
        # self.dataloader.collate_fn = gandraw_dataset.collate_data
        self.cross_entropy_loss = nn.CrossEntropyLoss().cuda()
        self.output_dir = self.cfg.results_path
        
        self.image_transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])])        
        self.unorm = UnNormalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))

        #self.unk_embedding = np.load("unk_embedding.npy")
        self.word2index = {k: v for v, k in enumerate(self.vocab)}
        self.index2word = {v: k for v, k in enumerate(self.vocab)}
        self.previous_output_utt = None

    def load_img(self, input_img, resize_wh=128):
        r"""
        input_img should be a three dimensional numpy matrix
        """
        if input_img.shape[0] > resize_wh:
            input_img = cv2.resize(input_img, (resize_wh, resize_wh), interpolation=cv2.INTER_AREA)
        
        processed_input_img = self.image_transform(input_img).numpy()
        processed_input_img = np.expand_dims(processed_input_img, axis=0)
        return torch.FloatTensor(processed_input_img)

    def utt2ids(self, input_text):
        #Tokenize the input_text
        teller_text_tokens = ['<teller>'] + nltk.word_tokenize(self.previous_output_utt)
        drawer_text_tokens = ['<drawer>'] + nltk.word_tokenize(input_text)
        all_tokens = teller_text_tokens + drawer_text_tokens
        all_tokens_ids = [0] + [self.word2index.get(x, self.word2index['<unk>']) for x in all_tokens if x!= "<teller>" and x!= "<drawer>"]+[1]
        all_tokens_len = len(all_tokens_ids)
        
        turn_teller_drawer_ids = np.array(all_tokens_ids)
        turn_teller_drawer_ids = np.expand_dims(turn_teller_drawer_ids, axis=0)
        turn_teller_drawer_ids_len = np.ones((1))*all_tokens_len
        
        return torch.LongTensor(turn_teller_drawer_ids), torch.LongTensor(turn_teller_drawer_ids_len)
    def reset_teller(self):
        self.previous_output_utt = None
        self.model.reset_teller()
    
    def import_tgt_img(self, target_image):
        target_image = self.load_img(target_image)
        self.model.import_tgt_img(target_image)

    def generate_utt(self, input_img=None, input_utt=None):
        #concate output_utt and  input_utt
        if input_img is not None and input_utt is not None:
            input_img = self.load_img(input_img)
            input_utt_ids, input_utt_len = self.utt2ids(input_utt)
        else:
            input_utt_ids = None
            input_utt_len = None
        output_utt, stop =  self.model.generate_utt(input_img,input_utt_ids, input_utt_len, self.word2index, self.index2word)
        #update self.previous_output_utt
        self.previous_output_utt = output_utt
        return  output_utt, stop

    def first_utterance(self, convo_id):
        #TODO: provide tgt_img to data
        synth, seg_map, peek = Store.target_image_data(convo_id)
        tgt_img = byte_string_to_cv2(synth) #Expected to by a 3D numpy matrix imported using cv2

        #reset the teller
        self.reset_teller()
        #load tgt_img
        self.import_tgt_img(tgt_img)

        output_utt = self.generate_utt()
        #generate the utterance
        return output_utt
    
    def speak(self, image, convo_id, drawer_utt):
        # print("about to load data")
        data = Store.load_data(convo_id)
        if self.mode == ModelMode.silent:
            drawer_utt = random.choice(["Okay",  "Done", "Next"])
        # print("Calling generate...")
        output_utt, terminate_dialog =  self.generate_utt(byte_string_to_cv2(image), drawer_utt)
        print("Model:", output_utt, terminate_dialog)
        # print("utterance...?")
        # print(output_utt)
        data["should_finish"] = terminate_dialog
        Store.save_data(convo_id, data)        
        if "<" in output_utt or ">" in output_utt:
            data["should_finish"] = True
            Store.save_data(convo_id, data)
            return "okay, I think we're done. please send me one more message to confirm this."
        if data["should_finish"] or GameSelector.can_submit(convo_id):
            return "okay, I think we're done"
        return output_utt        
        
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
    
    #todo update this to select an image 
    @classmethod
    def target_image(cls):
        path = os.path.join(os.getcwd(), "target_images/")
        synth = choice([x for x in os.listdir(path) if ".jpg" in x])
        real = synth.replace(".jpg", ".png")
        return synth, real

    @classmethod
    def init_game(cls, convo_id, user_type, first_utterance="Hello world!"):       
        if GameSelector.game_exists(convo_id): return 
        data = Store.load_data(convo_id)
        data['user_type'] = user_type.value
        data['first_bot_utt'] = ""
        Store.save_data(convo_id, data)

    @classmethod
    def update_target_image(cls, convo_id, target_image):               
        data = Store.load_data(convo_id)        
        data['target_image']['synth'] = target_image+".jpg"
        data['target_image']['seg_map'] = target_image+"_seg.png"
        Store.save_data(convo_id, data)        
    
    @classmethod
    def set_first_utt(cls, convo_id, first_utterance="hello"):
        data = Store.load_data(convo_id)
        if len(data['first_bot_utt']) > len("hello"): return
        # print("First utterance is:", first_utterance)
        user_type = data['user_type']                
        data['first_bot_utt'] = "Teller: " + first_utterance
        Store.save_data(convo_id, data)

    @classmethod
    def game_exists(cls, convo_id):
        return os.path.exists(os.path.join(os.getcwd(), "saved_data/", f"{convo_id}.json"))

    @classmethod
    def can_submit(cls, convo_id):
        data = Store.load_data(convo_id)
        if data["should_finish"] == True: return True
        num_turns = len(data['dialog'])
        if data['user_type'] == UserType.silent_drawer.value or data['user_type'] == UserType.talkative_drawer.value:
            return num_turns >= 10
        return num_turns >= 10

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
        data = {"convo_id":convo_id, "dialog":[], "target_image":{"synth":target_synth, "seg_map":target_seg, "most_recent_peek_image":""}, "first_bot_utt":"", "token":GameSelector.token(), "num_peeks_left":2, "should_finish":False}                
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
        other_user = "Drawer"
        if data['user_type'] == UserType.talkative_teller.value or data['user_type'] == UserType.silent_teller.value:
            other_user = "Teller"
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