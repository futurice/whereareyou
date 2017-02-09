import json
import yaml
from flask import request, render_template
from models import Location, Detection, TrainingDetection, Measurement, app, db
from utils import get_mac_from_request


def seed():
    with open("locations.yml", 'r') as stream:
        try:
            locations = yaml.load(stream)
            for l in locations:
                db.session.add(Location(l))
            db.session.commit()
        except yaml.YAMLError as exc:
            print(exc)


@app.route('/')
def root():
    client_mac = get_mac_from_request(request)
    headers = ['MAC']
    headers.extend([l.value for l in Location.query.all()])
    macs = [t.mac for t in TrainingDetection.query.group_by('mac').all()]
    home_json = dict()
    for mac in macs:
        home_json[mac] = dict()
        for location in locations:
            l = Location.query.filter_by(value=location).first()
            home_json[mac][location] = (TrainingDetection.query.filter_by(mac=mac, location=l).first() is not None)
    return render_template('home.html', headers=headers, home_json=home_json)


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route("/status")
def status():
    return json.dumps([d.serialize() for d in Detection.query.all()])


@app.route('/locations')
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


if __name__ == "__main__":
    app.run(host='0.0.0.0')
