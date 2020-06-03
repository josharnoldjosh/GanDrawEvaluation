from config import config
from uuid import uuid4
from api import API
import os

# Mturk API
api = API()

# Clear hit data
# api.clear_hit_data()

# Define Task Type
bot_type = 'teller'
user_type = 'drawer'

# Target images
target_images = [x.split(".")[0] for x in os.listdir("target_image_eval/") if ".jpg" in x]

# Create hits
for hit_idx in range(len(target_images)):

    # Load question
    question_sample = open(f"./MTurk/{user_type}.xml", "r").read()

    # Task URLs
    # silent_url = f"https://language.cs.ucdavis.edu/visualchat/silent/{bot_type}/{target_images[hit_idx]}/{str(uuid4())[:8]}/"
    talkative_url = f"https://language.cs.ucdavis.edu/visualchat/talkative/{bot_type}/{target_images[hit_idx]}/{str(uuid4())[:8]}/"

    # Sample Validation questions
    # question_sample = question_sample.replace('${silent_task_link}', silent_url)   
    question_sample = question_sample.replace('${talkative_task_link}', talkative_url)

    # Create hit
    api.create_hit(question_sample)