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
    locations = [l.value for l in Location.query.all()]
    headers = ['MAC']
    headers.extend(locations)
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


@app.route('/get_mac')
def get_mac():
    mac = get_mac_from_request(request)
    return "Wasn't able to identify MAC address" if mac is None else mac


if __name__ == "__main__":
    app.run(host='0.0.0.0')
