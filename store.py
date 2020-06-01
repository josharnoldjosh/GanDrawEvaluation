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

try:
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
except:
    print("Failed to load geneva")

from math import sqrt

import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence
from torchvision import transforms
from teller_utils import UnNormalize

from drawer_utils import _parse_glove

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

class BotMode(Enum):
    silent=0
    talkative=1

class TellerBot():
    def __init__(self, cfg, pretrained_model_path=None, iteration=6000):
        self.cfg = cfg
        self.cfg.batch_size = 1
        self.bot_mode = BotMode.silent
        self.first_utt_called = False

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

        data = Store.load_data(convo_id)
        if data['first_bot_utt'] != "":
            print("First bot utterance is already set...")
            return "An error has occured.", False

        print("RESETING TELLER!!!")

        # if self.first_utt_called:
            # return "first utterance already called...?", False

        #TODO: provide tgt_img to data
        synth, seg_map, peek = Store.target_image_data(convo_id)
        tgt_img = byte_string_to_cv2(synth) #Expected to by a 3D numpy matrix imported using cv2

        #reset the teller
        self.reset_teller()
        #load tgt_img
        self.import_tgt_img(tgt_img)

        output_utt = self.generate_utt()
        #generate the utterance

        self.first_utt_called = True

        return output_utt
    
    def speak(self, image, convo_id, drawer_utt):
        # print("about to load data")
        data = Store.load_data(convo_id)

        # If silent or not
        if self.bot_mode == BotMode.silent:
            drawer_utt = random.choice(["Okay",  "Done", "Next"])

        # print("Calling generate...")
        output_utt, terminate_dialog =  self.generate_utt(byte_string_to_cv2(image), drawer_utt)
        print("Model:", output_utt, terminate_dialog)
        # print("utterance...?")
        # print(output_utt)
        data["should_finish"] = terminate_dialog
        Store.save_data(convo_id, data)        

        if "<" in output_utt or ">" in output_utt:
            return "okay, I think we're done. please send me one more message to confirm this."

        if data["should_finish"] or GameSelector.can_submit(convo_id):
            return "okay, I think we're done"

        return output_utt        
        
class SilentDrawerBot():
    def __init__(self, cfg, pretrained_model_path=None, iteration=1000):
        self.cfg = cfg
        gandraw_vocab_path = "/home/jarnold9/GanDraw/data/drawer/gandraw_vocab.txt"
        with open(gandraw_vocab_path, 'r') as f:
            gandraw_vocab = f.readlines()
            gandraw_vocab = [x.strip().rsplit(' ', 1)[0] for x in gandraw_vocab]        
        self.vocab = ['<s_start>', '<s_end>', '<unk>', '<pad>', '<d_end>'] + gandraw_vocab        
        self.cfg.vocab_size = len(self.vocab)
        self.model = INFERENCE_MODELS[cfg.gan_type](cfg)
        #load the pretrained_model
        if pretrained_model_path is not None:
            self.model.load(pretrained_model_path,iteration)
        
        self.bot_mode = BotMode.silent
        self.visualize_batch = 0
        # Keep all the progress images to be processed.
        self.visualize_images = []
        
        self.default_drawer_utt = ["okay", "done", "next"]
        glove_gandraw_path = "/home/jarnold9/GanDraw/data/drawer/glove_gandraw.txt"
        self.glove = _parse_glove(glove_gandraw_path)
        self.unk_embedding = np.load("/home/jarnold9/GanDraw/GeNeVA/unk_embedding.npy")
        self.get_background_embedding()
        self.output_image = None
        self.reset_drawer()

    def get_background_embedding(self):
        self.background_embedding = np.zeros((self.cfg.img_size, self.cfg.img_size, 22), dtype=np.int32)
        self.background_embedding[:,:,0] = 1 #Define the background with sky label activated
        self.background_embedding =  np.expand_dims(self.background_embedding, axis=0)
        self.background_embedding = self.process_image(self.background_embedding)
        self.background_embedding = torch.FloatTensor(self.background_embedding)

    def generate_im(self, input_text):
        #TODO: build the function to generate_im
        with torch.no_grad():
            current_turn_embedding, current_turn_len = self.utt2embedding(input_text)
            gen_im = self.model.generate_im(current_turn_embedding, current_turn_len)
            gen_im = self.post_processing_im(gen_im)
        return gen_im

    def utt2embedding(self, input_text):
        #Tokenize the input_text
        text_tokens = ['<teller>'] + nltk.word_tokenize(input_text)
        sampled_drawer_utt = ['<drawer>']+nltk.word_tokenize(random.choice(self.default_drawer_utt))
        text_tokens = text_tokens + sampled_drawer_utt
        #get padded_input_text
        processed_text_tokens =  [w for w in text_tokens if w not in string.punctuation]
        processed_text_len = len(processed_text_tokens)
        #initialize turn embedding 
        turn_embeddings = np.zeros((processed_text_len, 300))
        for i,w in enumerate(processed_text_tokens):
            turn_embeddings[i] = self.glove.get(w, self.unk_embedding)
        #turns_embeddings is not a numpy matrix
        turn_embeddings = np.expand_dims(turn_embeddings, axis=0)
        turn_lens = np.ones((1))*processed_text_len        
        return torch.FloatTensor(turn_embeddings), torch.LongTensor(turn_lens)

    def reset_drawer(self):
        self.output_image = None
        self.model.reset_drawer(self.background_embedding)
        #self.model.eval()

    def post_processing_im(self, gen_im,resize_wh=512):
        dominant_label = np.unique(gen_im)
        output_image = cv2.resize(gen_im, (resize_wh, resize_wh), interpolation=cv2.INTER_AREA)
        output_image = self.smooth_segmentation(output_image, dominant_label)
        return output_image

    def smooth_segmentation(self, image, dominant_label):        
        """
        image is the 3D gray scale image with each pixel equal to the label of a certain category.
        return the same size of shrinked_image with only dominant_label
        """
        drawing2landscape = [
            ([0, 0, 0],156), #sky
            ([156, 156, 156], 156),#sky
            ([154, 154, 154], 154), #sea
            ([134, 134, 134], 134), #mountain
            ([149, 149, 149], 149), #rock
            ([126, 126, 126], 126), #hill
            ([105, 105, 105], 105), #clouds
            ([14, 14, 14], 14), #sand
            ([124, 124, 124], 124), #gravel
            ([158, 158, 158], 158), #snow
            ([147, 147, 147], 147), #river
            ([96, 96, 96], 96), #bush
            ([168, 168, 168], 168), #tree
            ([148, 148, 148], 148), #road
            ([110, 110, 110], 110), #dirt 
            ([135, 135, 135], 135), #mud 
            ([119, 119, 119], 119), #fog 
            ([161, 161, 161], 161), #stone
            ([177, 177, 177], 177), #water
            ([118, 118, 118], 118), #flower
            ([123, 123, 123], 123), #grass
            ([162, 162, 162], 162), #straw
        ]

        center = []
        for l in dominant_label:
            center_array = np.array([l]*3)
            center.append(np.uint8(center_array))
        #print(center)
        for i in range(image.shape[0]):
            for j in range(image.shape[1]):
                current_pixel = np.uint8(image[i,j])
                #sort centers

                if not any(all(current_pixel == x) for x in center):
                    #print("sort_center")
                    center.sort(key=lambda c: sqrt((current_pixel[0]-c[0])**2+(current_pixel[1]-c[1])**2+(current_pixel[2]-c[2])**2))
                    image[i,j] = center[0]
        #print(image)
        return image

    def process_image(self, images):
        if self.cfg.image_gen_mode == "real":
            result_images = np.zeros_like(
                images.transpose(0, 3, 1, 2), dtype=np.float32)
            for i in range(images.shape[0]):
                current_img = images[i]
                current_processed_img = self.image_transform(current_img)
                current_processed_img = current_processed_img.numpy()
                result_images[i] = current_processed_img
        
        elif self.cfg.image_gen_mode == "segmentation":
            result_images = images[..., ::-1]
            #print(result_images.shape)
            result_images = result_images / 128. - 1
            result_images += np.random.uniform(size=result_images.shape, low=0, high=1. / 64)
            result_images = result_images.transpose(0, 3, 1, 2)
        elif self.cfg.image_gen_mode == "segmentation_onehot":
            #We don't preprocess the image in this setting, switch the channel to the second dimension
            result_images = images.transpose(0,3,1,2)
        return result_images
        
    def speak(self, convo_id, teller_utt):
        data = Store.load_data(convo_id)        
        self.drawer_utt = random.choice(self.default_drawer_utt)
        self.output_image = self.generate_im(teller_utt)
        return self.drawer_utt, self.output_image

    def peek(self, convo_id):
        return self.output_image

class TalkativeDrawerBot():
    def __init__(self, cfg, pretrained_model_path=None, iteration=1000):
        self.cfg = cfg
        gandraw_vocab_path = "/home/jarnold9/GanDraw/data/drawer/gandraw_vocab.txt"
        with open(gandraw_vocab_path, 'r') as f:
            gandraw_vocab = f.readlines()
            gandraw_vocab = [x.strip().rsplit(' ', 1)[0] for x in gandraw_vocab]        
        self.vocab = ['<s_start>', '<s_end>', '<unk>', '<pad>', '<d_end>'] + gandraw_vocab        
        self.cfg.vocab_size = len(self.vocab)

        self.model = INFERENCE_MODELS[cfg.gan_type](cfg)
        #load the pretrained_model
        if pretrained_model_path is not None:
            self.model.load(pretrained_model_path,iteration)
        
        #self.bot_mode = BotMode.silent
        self.visualize_batch = 0
        # Keep all the progress images to be processed.
        self.visualize_images = []
        
        self.default_drawer_utt = ["okay", "done", "next"]
        glove_gandraw_path = "/home/jarnold9/GanDraw/data/drawer/glove_gandraw.txt"
        self.glove = _parse_glove(glove_gandraw_path)
        self.unk_embedding = np.load("/home/jarnold9/GanDraw/GeNeVA/unk_embedding.npy")
        self.get_background_embedding()
        self.output_image = None
        self.reset_drawer()
    def get_background_embedding(self):
        self.background_embedding = np.zeros((self.cfg.img_size, self.cfg.img_size, 22), dtype=np.int32)
        self.background_embedding[:,:,0] = 1 #Define the background with sky label activated
        self.background_embedding =  np.expand_dims(self.background_embedding, axis=0)
        self.background_embedding = self.process_image(self.background_embedding)
        self.background_embedding = torch.FloatTensor(self.background_embedding)
        
    def generate_im_utt(self, input_text):
        #TODO: build the function to generate_im
        with torch.no_grad():
            current_turn_embedding, current_turn_len = self.utt2embedding(input_text)
            #Get the user ids as well
            input_utt_ids, input_utt_ids_len = self.utt2ids(input_text)
            gen_im, output_utt = self.model.generate_im_utt(current_turn_embedding, current_turn_len, input_utt_ids, input_utt_ids_len, self.word2index, self.index2word)
            self.prev_utt = output_utt
            gen_im = self.post_processing_im(gen_im)
        return gen_im, output_utt
    
    def utt2ids(self, input_text):
        #Tokenize the input_text
        if self.prev_utt is not None:
            drawer_text_tokens = ['<drawer>'] + nltk.word_tokenize(self.prev_utt)
        else:
            drawer_text_tokens = []
        teller_text_tokens = ['<teller'] + nltk.word_tokenize(input_text)
        all_tokens = drawer_text_tokens + teller_text_tokens
        all_tokens_ids = [0] + [self.word2index.get(x, self.word2index['<unk>']) for x in all_tokens if x!= "<teller>" and x!= "<drawer>"]+[1]
        all_tokens_len = len(all_tokens_ids)
        
        turn_teller_drawer_ids = np.array(all_tokens_ids)
        turn_teller_drawer_ids = np.expand_dims(turn_teller_drawer_ids, axis=0)
        turn_teller_drawer_ids_len = np.ones((1))*all_tokens_len
        
        return torch.LongTensor(turn_teller_drawer_ids), torch.LongTensor(turn_teller_drawer_ids_len)
    
    def utt2embedding(self, input_text):
        #Tokenize the input_text
        text_tokens = ['<teller>'] + nltk.word_tokenize(input_text)
        #sampled_drawer_utt = ['<drawer>']+nltk.word_tokenize(random.choice(self.default_drawer_utt))
        if self.prev_utt is not None:
            sampled_drawer_utt = ['<drawer>'] + nltk.word_tokenize(self.prev_utt)
        else:
            sampled_drawer_utt = []
        text_tokens = sampled_drawer_utt + text_tokens
        #get padded_input_text
        processed_text_tokens =  [w for w in text_tokens if w not in string.punctuation]
        processed_text_len = len(processed_text_tokens)
        #initialize turn embedding 
        turn_embeddings = np.zeros((processed_text_len, 300))
        for i,w in enumerate(processed_text_tokens):
            turn_embeddings[i] = self.glove.get(w, self.unk_embedding)
        #turns_embeddings is not a numpy matrix
        turn_embeddings = np.expand_dims(turn_embeddings, axis=0)
        turn_lens = np.ones((1))*processed_text_len
        
        return torch.FloatTensor(turn_embeddings), torch.LongTensor(turn_lens)
    def reset_drawer(self):
        self.model.reset_drawer(self.background_embedding)
        self.prev_utt = None
        #self.model.eval()
    def post_processing_im(self, gen_im,resize_wh=512):
        dominant_label = np.unique(gen_im)
        output_image = cv2.resize(gen_im, (resize_wh, resize_wh), interpolation=cv2.INTER_AREA)
        output_image = self.smooth_segmentation(output_image, dominant_label)
        return output_image
    def smooth_segmentation(self, image, dominant_label):
        """
        image is the 3D gray scale image with each pixel equal to the label of a certain category.
        return the same size of shrinked_image with only dominant_label
        """
        drawing2landscape = [
            ([0, 0, 0],156), #sky
            ([156, 156, 156], 156),#sky
            ([154, 154, 154], 154), #sea
            ([134, 134, 134], 134), #mountain
            ([149, 149, 149], 149), #rock
            ([126, 126, 126], 126), #hill
            ([105, 105, 105], 105), #clouds
            ([14, 14, 14], 14), #sand
            ([124, 124, 124], 124), #gravel
            ([158, 158, 158], 158), #snow
            ([147, 147, 147], 147), #river
            ([96, 96, 96], 96), #bush
            ([168, 168, 168], 168), #tree
            ([148, 148, 148], 148), #road
            ([110, 110, 110], 110), #dirt 
            ([135, 135, 135], 135), #mud 
            ([119, 119, 119], 119), #fog 
            ([161, 161, 161], 161), #stone
            ([177, 177, 177], 177), #water
            ([118, 118, 118], 118), #flower
            ([123, 123, 123], 123), #grass
            ([162, 162, 162], 162), #straw
        ]

        center = []
        for l in dominant_label:
            center_array = np.array([l]*3)
            center.append(np.uint8(center_array))
        #print(center)
        for i in range(image.shape[0]):
            for j in range(image.shape[1]):
                current_pixel = np.uint8(image[i,j])
                #sort centers

                if not any(all(current_pixel == x) for x in center):
                    #print("sort_center")
                    center.sort(key=lambda c: sqrt((current_pixel[0]-c[0])**2+(current_pixel[1]-c[1])**2+(current_pixel[2]-c[2])**2))
                    image[i,j] = center[0]
        #print(image)
        return image
    def process_image(self, images):
        if self.cfg.image_gen_mode == "real":
            result_images = np.zeros_like(
                images.transpose(0, 3, 1, 2), dtype=np.float32)
            for i in range(images.shape[0]):
                current_img = images[i]
                current_processed_img = self.image_transform(current_img)
                current_processed_img = current_processed_img.numpy()
                result_images[i] = current_processed_img
        
        elif self.cfg.image_gen_mode == "segmentation":
            result_images = images[..., ::-1]
            #print(result_images.shape)
            result_images = result_images / 128. - 1
            result_images += np.random.uniform(size=result_images.shape, low=0, high=1. / 64)
            result_images = result_images.transpose(0, 3, 1, 2)
        elif self.cfg.image_gen_mode == "segmentation_onehot":
            #We don't preprocess the image in this setting, switch the channel to the second dimension
            result_images = images.transpose(0,3,1,2)
        return result_images

    def speak(self, convo_id, teller_utt):
        data = Store.load_data(convo_id)    
        #self.drawer_utt = # ...?
        # if self.bot_mode == BotMode.silent:
        #     self.drawer_utt = random.choice(self.default_drawer_utt)
        self.output_image, self.drawer_utt = self.generate_im_utt(teller_utt)
        return self.drawer_utt, self.output_image

    def peek(self, convo_id):
        return self.output_image

class GameSelector:
    
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
        data['target_image']['synth'] = target_image + ".jpg"
        data['target_image']['seg_map'] = target_image + "_seg.png"
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
        elif synth and not seg_map and not style:
            data["dialog"].append({"user":Store.preprocess_string(user_utt), "bot":Store.preprocess_string(bot_utt), "synth":synth, "generated_from_drawer_bot":True})            
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
    def get_seg_data(cls, convo_id):
        data = Store.load_data(convo_id)
        return [turn['seg_map'] for turn in data['dialog']]            
            
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