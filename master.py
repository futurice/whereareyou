"""Master Logic and Routing"""

from app import app, db, Location, Detection, TrainingDetection, Measurement, \
                is_futurice_employee
from flask import request, render_template
from flask_login import login_required
from utils import get_mac_from_request
import json
import os
import yaml


def seed():
    with open("locations.yml", 'r') as stream:
        try:
            for l in yaml.load(stream):
                db.session.add(Location(l))
            db.session.commit()
        except yaml.YAMLError as exc:
            print(exc)


@app.route('/')
@login_required
@is_futurice_employee
def index():
    client_mac = get_mac_from_request(request)
    headers = ['MAC']
    locations = [l.value for l in Location.query.all()]
    headers.extend(locations)
    macs = [t.mac for t in TrainingDetection.query.group_by('mac').all()]
    home_json = dict()
    for mac in macs:
        home_json[mac] = dict()
        for location in locations:
            l = Location.query.filter_by(value=location).first()
            home_json[mac][location] = (TrainingDetection.query.filter_by(mac=mac, location=l).first() is not None)
    return render_template('index.html', headers=headers, home_json=home_json)

@app.route('/dashboard')
@login_required
@is_futurice_employee
def dashboard():
    return render_template('dashboard.html')


@app.route("/status")
@login_required
@is_futurice_employee
def status():
    return json.dumps([d.serialize() for d in Detection.query.all()])


@app.route('/locations')
@login_required
@is_futurice_employee
def locations():
    return json.dumps([l.serialize() for l in Location.query.all()])


@app.route('/update', methods=['POST'])
@login_required
@is_futurice_employee
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
