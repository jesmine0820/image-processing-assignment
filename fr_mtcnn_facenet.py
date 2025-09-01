import cv2
import pickle
import numpy as np
from mtcnn import MTCNN
from keras_facenet import FaceNet
from sklearn.metrics.pairwise import cosine_similarity

# Initialize detector and embedder
detector_mtcnn = MTCNN()
embedder = FaceNet()

# get the database
with open("database/facenet_embeddings.pkl", "rb") as file:
    face_database = pickle.load(file)

def l2_normalize(x):
    return x / np.linalg.norm(x)

# Get top N matches with cosine similarity
def get_top_matches(face_img, database, top_n=3):
    face_img = cv2.resize(face_img, (160, 160))
    embedding = embedder.embeddings([face_img])[0]
    embedding = l2_normalize(embedding)

    similarities = []
    for name, db_emb in database.items():
        sim_score = cosine_similarity([embedding], [db_emb])[0][0]  # Higher is better
        similarities.append((name, sim_score))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_n]