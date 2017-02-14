"""Master Logic and Routing"""

from app import app, db, User, Location, Detection, TrainingDetection, \
                is_employee, Measurement, Device
from flask import request, render_template, make_response
from flask_login import login_required, current_user
from utils import get_mac_from_request
import json
import os
import yaml


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
        training_json[mac] = {'avatar_url': user.avatar}
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
@login_required
@is_employee
def index():
    ask_for_adding = False
    client_mac = get_mac_from_request(request)
    client_mac = 'AC'
    locations = [l.value for l in Location.query.all()]
    training_macs = [t.mac for t in TrainingDetection.query.group_by('mac').all()]
    current_detected_macs = [d.mac for d in Detection.query.filter_by(type='detection').all()]
    champions, training_json = get_training_table(training_macs, locations)

    if client_mac in current_detected_macs:
        ask_for_adding = True

    return render_template('index.html', **get_context(champions=champions,
                           training_json=training_json,
                           ask_for_adding=ask_for_adding,
                           locations=locations, mac=client_mac))


@app.route('/dashboard')
@login_required
@is_employee
def dashboard():
    return render_template('dashboard.html', **get_context())


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
    macs = list(df.mac.unique())
    locations = list(df.location.unique())
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
    for entry in data:
        mac = entry['mac']
        slave_id = entry['slave_id']
        power = int(entry['power'])

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
        else:
            measurement = Measurement(slave_id, power, detection)
            db.session.add(measurement)
    db.session.commit()
    return "Updated measurement of " + str(len(data)) + " entries"


@app.route('/add_training', methods=['POST'])
def add_training():
    if current_user.is_anonymous:
        return "Sorry but you must be logged in to add training data."
    mac = request.form['mac']
    location = request.form['location']
    current_detection = Detection.query.filter_by(type='detection', mac='AC').all()[0]
    training_detection = TrainingDetection(location=Location.query.filter_by(value=location).all()[0], mac=mac)
    db.session.add(training_detection)
    for m in current_detection.measurements:
        measurement = Measurement(m.slave_id, m.power, training_detection)
        db.session.add(measurement)
    db.session.commit()
    user = User.query.filter_by(email=current_user.email).first()
    if not Device.query.filter_by(user=user, mac=mac).first():
        db.session.add(Device(mac=mac, user=user))
        db.session.commit()
    return index()


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
