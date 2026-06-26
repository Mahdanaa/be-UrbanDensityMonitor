import numpy as np
import pickle
import os

MODEL_PATH = "app/models/density_cluster_model.pkl"

def predict_density(person_count, vehicle_count, is_raining=False):
    if vehicle_count == 0:
        if person_count > 20: return "Anomaly"
        else: return "Low Density"

    if is_raining and vehicle_count > 10:
        return "Anomaly"

    person_vehicle_ratio = person_count / vehicle_count if vehicle_count > 0 else 0.0

    if person_vehicle_ratio > 3.0 and person_count > 15:
        return "Anomaly"

    if not os.path.exists(MODEL_PATH):
        if vehicle_count < 15: return "Low Density"
        elif vehicle_count < 40: return "Medium Density"
        else: return "High Density"

    with open(MODEL_PATH, "rb") as f:
        kmeans_model = pickle.load(f)

    input_data = np.array([[person_count, vehicle_count, person_vehicle_ratio]])
    cluster_id = kmeans_model.predict(input_data)[0]

    if cluster_id == 0: return "Low Density"
    elif cluster_id == 1: return "Medium Density"
    else: return "High Density"
