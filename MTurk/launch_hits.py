from api import API
from config import config
from uuid import uuid4

# Mturk API
api = API()

# Clear hit data
api.clear_hit_data()

# Options:
# teller
# drawer
user_type = 'drawer'

# Create hits
for hit_idx in range(config['num_hits']):

    # Load question
    question_sample = open(f"./MTurk/{user_type}.xml", "r").read()

    # Token
    token = str(uuid4())[:8]

    # Task URL
    url = f"https://language.cs.ucdavis.edu/visualchat/{user_type}/{token}/"

    # Sample Validation questions
    question_sample = question_sample.replace('${task_link}', url)   

    # Create hit
    api.create_hit(question_sample)
