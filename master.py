from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from utils import get_mac_from_request
import os
import datetime
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.getcwd() + '/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)


class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.String(80), unique=True)
    last_updated = db.Column(db.DateTime)

    def __init__(self, mac):
        self.mac = mac
        self.last_updated = datetime.datetime.now()

    def __repr__(self):
        return '<Detection %r (%r)>' % (self.mac, str(self.last_updated))


class Measurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slave_id = db.Column(db.String)
    power = db.Column(db.Integer)
    detection_id = db.Column(db.Integer, db.ForeignKey('detection.id'))
    detection = db.relationship('Detection', backref=db.backref('measurements', lazy='dynamic'))

    def __init__(self, slave_id, power, detection):
        self.slave_id = slave_id
        self.power = power
        self.detection = detection

    def __repr__(self):
        return '<Measurement %r %r (%r)>' % (self.slave_id, self.power, self.detection)

def detection_to_dict(detection):
    detection_dict = {'mac':detection.mac}
    detection_dict["measurements"] = []
    for m in detection.measurements.all():
        detection_dict["measurements"].append({'power': m.power, 'slave_id': m.slave_id})
    return detection_dict

@app.route('/dashboard')
def dashboard():
    return """

<!DOCTYPE html>
<html>
  <head>
    <script type="text/javascript" src="http://smoothiecharts.org/smoothie.js"></script>
    <script src="https://code.jquery.com/jquery-1.11.3.js"></script>
    <script type="text/javascript">

      var cellphone = new TimeSeries();
      var ipod = new TimeSeries();
      setInterval(function() {
        $.getJSON( "/status", function( data ) {
        c1 = data[0]["measurements"][0]["power"];
        c2 = data[1]["measurements"][0]["power"];
        console.log(c1)
        console.log(c2)
        cellphone.append(new Date().getTime(), c1);
        ipod.append(new Date().getTime(), c2);
        });
      }, 5000);

      function createTimeline() {
        var chart = new SmoothieChart({millisPerPixel:100, minValue:-100, maxValue:0});
        chart.addTimeSeries(cellphone, { strokeStyle: 'rgba(0, 255, 0, 1)', fillStyle: 'rgba(0, 255, 0, 0.2)', lineWidth: 4 });
        chart.addTimeSeries(ipod, { strokeStyle: 'rgba(0, 255, 255, 1)', fillStyle: 'rgba(0, 255, 255, 0.2)', lineWidth: 4 });
        chart.streamTo(document.getElementById("chart"), 500);
      }
    </script>
  </head>
  <body onload="createTimeline()">
  <canvas id="chart" width="1000" height="100"></canvas>
  </body>
</html>

    """


@app.route("/status")
def root():
    return json.dumps([detection_to_dict(d) for d in Detection.query.all()])


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


@app.route('/get_mac')
def get_mac():
    mac = get_mac_from_request(request)
    return "Wasn't able to identify MAC address" if mac is None else mac


if __name__ == "__main__":
    app.run()
