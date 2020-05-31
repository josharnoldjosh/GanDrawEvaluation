from shutil import copyfile
from secrets import randbelow
from pprint import pprint
import json
import os

test_data = json.load(open("./data_full_filtered_org/test.json"))['data']
length = len(test_data)

if not os.path.exists("./target_image_eval/"): os.mkdir("./target_image_eval/")

for i in range(10):
    result = randbelow(length)
    target = test_data[result]['target_image']
    print(result)
    copyfile(os.path.join(os.getcwd(), "data_full_filtered_org/", target), f"./target_image_eval/{target.split('/')[-1]}")