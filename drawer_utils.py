import numpy as np

def _parse_glove(glove_path):
    glove = {}
    with open(glove_path, 'r') as f:
        for line in f:
            splitline = line.split()
            word = splitline[0]
            embedding = np.array([float(val) for val in splitline[1:]])
            glove[word] = embedding

    return glove