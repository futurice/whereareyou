from sklearn.tree import DecisionTreeClassifier, export_graphviz
from sklearn.preprocessing import LabelEncoder
from sklearn.externals import joblib
import pandas as pd
import time
import os

MODEL_NAME = 'model.pkl'
MODEL_MAC_NAME = 'model_mac.pkl'
MAXIMUM_AGE = 5 * 60

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
    clf = DecisionTreeClassifier()
    clf.fit(df, y)
    joblib.dump(clf, model_name)
    if with_mac and mac_clf is None:
        mac_clf = clf
    if not with_mac and without_mac_clf is None:
        without_mac_clf = clf
    export_graphviz(clf, feature_names=["Power_" + slave_id for slave_id in df.columns],
                    class_names=y.unique(), filled=True, rounded=True, out_file='model.dot')
    os.system("dot -Tpng model.dot -o model.png")


def get_df_from_detection(detection_list):
    detection_data = []
    too_old = False
    for det in detection_list:
        json_data = det.serialize()
        for m in json_data["measurements"]:
            json_data[m["slave_id"]] = m["power"]
            # TODO: Fix timezone problem
            if time.time() + 60*60 - m["last_seen"] > MAXIMUM_AGE:
                too_old = True
        del json_data["measurements"]
        if too_old:
            too_old = False
            continue
        else:
            detection_data.append(json_data)
    df = pd.DataFrame(detection_data)
    return df


def predict_location(df):
    global without_mac_clf
    if without_mac_clf is None:
        without_mac_clf = joblib.load(MODEL_NAME)
    clf = without_mac_clf
    macs = df.pop("mac")
    df['predicted_location'] = clf.predict(df)
    df['mac'] = macs
    return df
