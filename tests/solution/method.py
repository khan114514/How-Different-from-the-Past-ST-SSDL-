"""Initial forecasting method. Implement fit and predict to change the method."""
import numpy as np


def fit(features, targets, seed):
    return {'method':'identity', 'version':1}


def predict(state, features):
    return np.array(features['base'], dtype=np.float32, copy=True)
