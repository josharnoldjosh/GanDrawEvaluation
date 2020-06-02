"""
Calculate the vocabulary usage
"""

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from collections import Counter
import json
import os

with open("data_full_filtered_org/data.json", "r") as file:
    data = json.load(file)

data = data['test'] + data['train'] + data['val']

teller_utterances = []
drawer_utterances = []

for convo in data:
    for turn in convo['dialog']:
        teller_utterances += [turn['teller']]
        drawer_utterances += [turn['drawer']]

teller = " ".join(teller_utterances)
drawer = " ".join(drawer_utterances)

teller = [x.replace(",", "").replace(".", "").replace("'", "").replace("!", "").replace("?", "").lower() for x in teller.split(" ") if x != " " and x not in stopwords.words('english')]
drawer = [x.replace(",", "").replace(".", "").replace("'", "").replace("!", "").replace("?", "").lower() for x in drawer.split(" ") if x != " " and x not in stopwords.words('english')]

teller = " ".join(teller)
drawer = " ".join(drawer)

teller = word_tokenize(teller)
drawer = word_tokenize(drawer)

teller = Counter(teller)
drawer = Counter(drawer)

print(teller.most_common(50))
print("---")
print(drawer.most_common(50))