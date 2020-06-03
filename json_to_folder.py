from calc_score import Seg2Real
from shutil import copyfile
from Helper import *
import json
import os

data = ["./saved_data/"+x for x in os.listdir("saved_data/") if ".json" in x]

if not os.path.exists("json_to_folder/"): os.mkdir("json_to_folder/")

def write_text(path, game):
    with open(f"{path}dialog.txt", "w") as file:
        if game['first_bot_utt'] != "": file.write("Bot: "+game['first_bot_utt']+"\n")
        for turn in game['dialog']:
            file.write(f"User: {turn['user']}\n")
            file.write(f"Bot: {turn['bot']}\n")

def write_image_data(path, game):
    for idx, turn in enumerate(game['dialog']):
        synth = byte_string_to_image(turn['synth'])
        seg_map = byte_string_to_image(turn['seg_map'])
        synth.save(f"{path}{idx}_synth.jpg")
        seg_map.save(f"{path}{idx}_seg_map.jpg")

def write_target_image(target_image, path, game):
    print(os.getcwd())
    copyfile(f"./target_image_eval/{target_image}.jpg", path+"target_image.jpg")

def write_score(path, game):
    score = "0.0"
    try:        
        last_drawn_image = byte_string_to_cv2(game['dialog'][-1]['seg_map'])        
        last_drawn_image = cv2.cvtColor(last_drawn_image, cv2.COLOR_BGR2RGB)
        last_drawn_image = last_drawn_image[:, :, 0]
        last_drawn_image = cv2.resize(last_drawn_image, (350, 350))
        seg_map = cv2.imread(f"./target_images/{game['target_image']['seg_map']}")
        seg_map = cv2.cvtColor(seg_map, cv2.COLOR_BGR2RGB)
        seg_map = seg_map[:, :, 0]
        seg_map = cv2.resize(seg_map, (350, 350))        
        score = Seg2Real().gaugancodraw_eval_metrics(last_drawn_image, seg_map, 182)
        score = str(round(score, 2))            
    except Exception as error:
        print(error)
    with open(f"{path}{score}.txt", "w") as file:        
        file.write(score)
        print("Wrote score!")

for json_file in data:
    with open(json_file, "r") as file:
        game = json.load(file)
        target_image = game['target_image']['synth'].split(".")[0]
        path = f"json_to_folder/{target_image}/"
        if not os.path.exists(path): os.mkdir(path)
        write_text(path, game)
        write_image_data(path, game)
        write_target_image(target_image, path, game)        
        write_score(path, game)