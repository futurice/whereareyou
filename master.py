"""Master Logic and Routing"""

from app import app, db, User, Location, Detection, TrainingDetection, \
                is_employee, Measurement, Device
from flask import request, render_template
from flask_login import login_required, current_user
from utils import get_mac_from_request
import json
import os
import yaml


def load_data():
    training = TrainingDetection(mac='AA', location=Location.query.all()[0])
    m1 = Measurement('slave1', -50, training)
    detection = Detection(mac='AC')
    m2 = Measurement('slave1', -80, detection)
    for x in [training, m1, detection, m2]:
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
        user = Device.query.filter_by(mac=mac).first().user
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
    return render_template('dashboard.html')


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


@app.route('/update', methods=['POST'])
def update():
    mac = request.form['mac']
    slave_id = request.form['slave_id']
    power = int(request.form['power'])

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
    return "Updated measurement of " + slave_id + " for " + mac + " with " + str(power)


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
    app.run(debug=True, threaded=True, **tls_params)
