from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.externals import joblib
import pandas as pd

MODEL_NAME = 'model.pkl'
MODEL_MAC_NAME = 'model_mac.pkl'

without_mac_clf = None
mac_clf = None

def train_models(data):
    #train_model(data, with_mac=True)
    train_model(data, with_mac=False)


def train_model(data, with_mac=True):
    global without_mac_clf, mac_clf
    df = pd.DataFrame.from_dict(data)
    y = df.pop("location")
    model_name = MODEL_MAC_NAME if with_mac else MODEL_NAME
    if with_mac:
        df = df.apply(LabelEncoder().fit_transform)
    else:
        df.drop("mac", axis=1, inplace=True)
    clf = RandomForestClassifier()
    clf.fit(df, y)
    joblib.dump(clf, model_name)
    if with_mac and mac_clf is None:
        mac_clf = clf
    if not with_mac and without_mac_clf is None:
        without_mac_clf = clf

def predict_location(det):
    global without_mac_clf
    if without_mac_clf is None:
        without_mac_clf = joblib.load(MODEL_NAME)
    clf = without_mac_clf
    json_data = det.serialize()
    for m in json_data["measurements"]:
        json_data[m["slave_id"]] = m["power"]
    del json_data["measurements"]
    del json_data["mac"]
    df = pd.DataFrame([json_data])
    return clf.predict(df)[0]
