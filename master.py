"""Master Logic and Routing"""

from app import app, db, User, Location, Detection, TrainingDetection, \
                is_employee, Measurement, Device
from training import train_models, predict_location, get_df_from_detection
from flask import request, render_template, make_response, redirect, url_for
from flask_login import login_required, current_user
from utils import get_mac_from_request
import datetime
import json
import os
import yaml
import pandas as pd


def load_data():
    mac1 = 'AC'
    mac2 = 'AD'
    powers1 = [-10, -30, -60]
    powers2 = [-20, -40, -70]
    for i in range(3):
        train = TrainingDetection(mac=mac1, location=Location.query.all()[i])
        m1 = Measurement('slave1', powers1[i], train)
        for x in [train, m1]:
            db.session.add(x)
    for i in range(3):
        train = TrainingDetection(mac=mac2, location=Location.query.all()[i])
        m1 = Measurement('slave1', powers2[i], train)
        for x in [train, m1]:
            db.session.add(x)
    db.session.commit()


def seed():
    with open("locations.yml", 'r') as stream:
        try:
            for l in yaml.load(stream):
                db.session.add(Location(l))
            db.session.commit()
        except yaml.YAMLError as exc:
            print(exc)


def get_current_detections():
    current_detection_ids = [d.id for d in Detection.query.filter_by(type='detection').all()]
    return [Detection.query.get(id).serialize() for id in current_detection_ids]


def get_training_table(training_macs, locations):
    training_json = dict()
    champions = []
    for mac in training_macs:
        is_champion = True
        device = Device.query.filter_by(mac=mac).first()
        if device:
            user = device.user
        else:
            continue
        training_json[mac] = {'avatar_url': user.avatar, 'email': user.email}
        for location in locations:
            l = Location.query.filter_by(value=location).first()
            training_json[mac][location] = (TrainingDetection.query.filter_by(mac=mac, location=l).first() is not None)
            if TrainingDetection.query.filter_by(mac=mac, location=l).first() is None:
                is_champion = False
        if is_champion:
            champions.append(user.avatar)
            del training_json[mac]
            continue
    return champions, training_json


def get_flattened_training_data():
    training_json = [d.serialize() for d in TrainingDetection.query.all()]
    for training in training_json:
        for m in training["measurements"]:
            training[m["slave_id"]] = m["power"]
        del training["measurements"]
        training["location"] = training["location"]["value"]
    return training_json


def get_context(**params):
    if params:
        view_params = params
    else:
        view_params = dict()
    view_params['user_email'] = current_user.email
    view_params['avatar_url'] = current_user.avatar
    return view_params


@app.route('/')
@app.route('/index')
@login_required
@is_employee
def index():
    ask_for_adding = False
    client_mac = get_mac_from_request(request)
    if client_mac is not None:
        client_mac = client_mac.upper()
    current_location = 'Not known, yet'
    locations = [l.value for l in Location.query.all()]
    training_macs = [t.mac for t in TrainingDetection.query.group_by('mac').all()]
    current_detected_macs = [d.mac for d in Detection.query.filter_by(type='detection').all()]
    champions, training_json = get_training_table(training_macs, locations)

    if client_mac in current_detected_macs:
        ask_for_adding = True
        try:
            current_location = predict_location(Detection.query.filter_by(type='detection', mac=client_mac).first())
        except Exception, e:
            print e

    return render_template('index.html', **get_context(champions=champions,
                           training_json=training_json,
                           ask_for_adding=ask_for_adding,
                           locations=locations, mac=client_mac,
                           current_location=current_location))


@app.route('/dashboard')
@login_required
@is_employee
def dashboard():
    locations = [l.value for l in Location.query.all()]
    df = get_df_from_detection(Detection.query.filter_by(type='detection').all())
    if len(df) > 0:
        df = predict_location(df)
    else:
        return render_template('dashboard.html', **get_context(current_locations=dict(locations, list())))
    df['user'] = '?'
    for index, row in df.iterrows():
        device = Device.query.filter_by(mac=row['mac']).first()
        if device:
            df.loc[index, 'user'] = device.user.email.split("@")[0]
    json_data = {}
    for l in locations:
        locations_df = df[df["predicted_location"] == l]
        json_data[l] = dict(zip(list(locations_df.mac), list(locations_df.user)))
    return render_template('dashboard.html', **get_context(current_locations=json_data))


@app.route("/status")
@login_required
@is_employee
def status():
    """Return current detections"""
    return json.dumps(get_current_detections())


@app.route("/users")
@login_required
@is_employee
def users():
    """Return users with devices"""
    return json.dumps([u.serialize() for u in User.query.all()])


@app.route('/locations')
@login_required
@is_employee
def locations():
    return json.dumps([l.serialize() for l in Location.query.all()])


@app.route('/training_data')
@login_required
@is_employee
def training_data():
    return json.dumps(get_flattened_training_data())


@app.route("/training_plot.png")
def training_plot():
    import StringIO
    import pandas as pd

    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure

    slave_id = request.args.get('slave_id', 'slave1')

    df = pd.DataFrame.from_dict(get_flattened_training_data())
    fig = Figure()
    plt = fig.add_subplot(111)

    colors = ['b', 'c', 'y', 'm', 'r']
    macs = list(df.mac.unique()) if len(df) > 0 else []
    locations = list(df.location.unique()) if len(df) > 0 else []
    plots = []

    plt.set_xlabel("MAC")
    plt.set_ylabel("Power")
    plt.set_yticks(range(-100, 0, 10), range(-100, 0, 10))
    plt.set_xticks(range(len(macs)))
    plt.set_xticklabels(macs)

    for location_index in range(len(locations)):
        sub_df = df.loc[df.location == locations[location_index]]
        mac_indices = [macs.index(m) for m in list(sub_df.mac)]
        plots.append(plt.scatter(mac_indices, sub_df[slave_id], marker='o', color=colors[location_index]))
    plt.legend(plots, locations, loc='upper right')

    canvas = FigureCanvas(fig)
    png_output = StringIO.StringIO()
    canvas.print_png(png_output)
    response = make_response(png_output.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response


@app.route('/update', methods=['POST'])
def update():
    data = request.get_json(silent=True)
    macs = []
    slave_id = data['slave_id']
    for entry in data['data']:
        mac = entry['mac']
        macs.append(mac)
        power = int(entry['power'])
        last_seen = float(entry['last_seen'])
        last_seen = datetime.datetime.fromtimestamp(last_seen)

        detection = Detection.query.filter_by(mac=mac).first()
        if not detection:
            detection = Detection(mac)
            db.session.add(detection)

        measurement = None
        for m in Detection.query.filter_by(mac=mac).first().measurements.all():
            if m.slave_id == slave_id:
                measurement = m
                break
        if measurement:
            measurement.power = power
            measurement.last_seen = last_seen
        else:
            measurement = Measurement(slave_id, power, last_seen, detection)
            db.session.add(measurement)
    # Set not occured MACs to -100 power
    detections = Detection.query.filter_by(type='detection').all()
    for d in detections:
        if d.mac not in macs:
            measurement = Measurement.query.filter_by(detection=d, slave_id=slave_id).first()
            if measurement.power != -100:
                print "setting " + d.mac + " from " + str(measurement.power) + " to -100"
                measurement.power = -100
    db.session.commit()
    return "Updated measurement of " + str(len(data)) + " entries"


@app.route('/add_training', methods=['POST'])
def add_training():
    if current_user.is_anonymous:
        return "Sorry but you must be logged in to add training data."
    mac = request.form['mac']
    location = request.form['location']
    current_detection = Detection.query.filter_by(type='detection', mac=mac).all()[0]
    training_detection = TrainingDetection(location=Location.query.filter_by(value=location).all()[0], mac=mac)
    db.session.add(training_detection)
    for m in current_detection.measurements:
        measurement = Measurement(m.slave_id, m.power, datetime.datetime.now(), training_detection)
        db.session.add(measurement)
    db.session.commit()
    user = User.query.filter_by(email=current_user.email).first()
    if not Device.query.filter_by(user=user, mac=mac).first():
        db.session.add(Device(mac=mac, user=user))
        db.session.commit()
    training_data = get_flattened_training_data()
    if len(training_data) > 0:
        train_models(training_data)
    return redirect(url_for('index'))


if __name__ == "__main__":
    generate_tls_certificate = os.environ.get("GENERATE_TLS_CERTIFICATE", True)
    tls_params = {}
    if generate_tls_certificate:
        """ SSL is required to use Google OAuth."""
        from werkzeug.serving import make_ssl_devcert
        if not os.path.isfile('ssl.crt') and not os.path.isfile('ssl.key'):
            make_ssl_devcert('./ssl', host='localhost')
        tls_params["ssl_context"] = ('./ssl.crt', './ssl.key')
    app.run(debug=True, host='0.0.0.0', threaded=True, **tls_params)
