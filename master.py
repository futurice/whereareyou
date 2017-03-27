"""Master Logic and Routing"""

from app import app, cache, db, User, Location, Detection, TrainingDetection, is_employee, Measurement, Device
from training import train_models, predict_location, get_df_from_detection, POWER_SLAVE_PREFIX
from flask import request, render_template, make_response, redirect, url_for
from flask_login import login_required, current_user
from utils import get_mac_from_request
import schedule
import datetime
import json
import os
import time
import math
import pandas as pd
import sys
import traceback
from xml.dom import minidom

AVATAR_WIDTH_HEIGHT = 25
OFFICE_MAPPING_PATH = 'static/office_mapping.json'
OFFICE_SVG_PATH = 'static/office.svg'
OLD_TIME_DELTA_DAYS = 1
OLD_TIME_DELTA_MINUTES = 5
CACHE_SHORT_TIME = 10
CACHE_LONG_TIME = 60


def remove_old_detections():
    db.session.query(Measurement).filter(Measurement.last_seen < datetime.datetime.utcnow() - datetime.timedelta(days=OLD_TIME_DELTA_DAYS)).delete()
    db.session.commit()
    for det in Detection.query.all():
        if len(det.measurements.all()) == 0:
            db.session.delete(det)
    print db.session.commit()


def load_locations():
    with open(OFFICE_MAPPING_PATH, 'r') as office_mapping:
        data = json.loads(office_mapping.read())
    for room_name in data.keys():
        db.session.add(Location(room_name))
    db.session.commit()


def measurement_too_old(measurement):
    return measurement.last_seen < datetime.datetime.utcnow() - datetime.timedelta(minutes=OLD_TIME_DELTA_MINUTES)


@cache.cached(timeout=CACHE_SHORT_TIME, key_prefix='current_detections')
def get_current_detections():
    current_detections = []
    for detection in Detection.query.filter_by(type='detection').all():
        for measurement in detection.measurements.all():
            if measurement_too_old(measurement):
                break
        current_detections.append(detection.serialize())
    return current_detections


@cache.cached(timeout=CACHE_LONG_TIME, key_prefix='current_locations')
def get_current_locations():
    locations = [l.value for l in Location.query.all()]
    df = get_df_from_detection(Detection.query.filter_by(type='detection').all())
    json_data = dict([(l, []) for l in locations])
    if len(df) > 0:
        df['user'] = '?'
        df['avatar'] = ''
        for index, row in df.iterrows():
            device = Device.query.filter_by(mac=row['mac']).first()
            if device:
                df.loc[index, 'user'] = device.user.name if device.user.name else device.user.email.split("@")[0].replace('.', ' ').title()
                df.loc[index, 'avatar'] = device.user.avatar
        df = df[df["user"] != '?']
        df["most_recent_seen"] = df["most_recent_seen"].apply(lambda timestamp: str(math.ceil((time.time() - timestamp) / 60)).split('.')[0] + " min")
        if len(df) > 0:
            df = predict_location(df)

    if len(df) > 0:
        df.drop(u"mac", inplace=True, axis=1)
        for l in locations:
            locations_df = df[df["predicted_location"] == l]
            json_data[l] = locations_df.to_dict(orient='records')
    return json_data


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
        training_json[mac] = {'avatar_url': user.avatar, 'name': device.user.name if device.user.name else device.user.email.split("@")[0].replace('.', ' ').title()}
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


def get_tag_item_by_id(doc, tag, id):
    for child in doc.getElementsByTagName(tag):
        if child.getAttribute('id') == id:
            return child
    return None


def get_office_map_with_persons():
        with open(OFFICE_SVG_PATH) as f:
            office_svg = f.read()
        location_data = get_current_locations()
        office_mapping = json.loads(open(OFFICE_MAPPING_PATH).read())
        svg_doc = minidom.parseString(office_svg)
        people_mappings = []

        for location in location_data:
            located_people = location_data[location]
            if len(located_people) > 0:
                x_offset = 0
                y_offset = 0
                svg_id = office_mapping[location]
                rect = get_tag_item_by_id(svg_doc, 'rect', svg_id)
                width, height = float(rect.getAttribute('width')), float(rect.getAttribute('height'))
                x, y = float(rect.getAttribute("x")), float(rect.getAttribute("y"))
                x += 1

                for person in location_data[location]:
                    remaining_width = width - x_offset * AVATAR_WIDTH_HEIGHT
                    if remaining_width < AVATAR_WIDTH_HEIGHT:
                        y_offset += 1
                        x_offset = 0
                    people_mappings.append(get_image_for_map(person["user"].replace(" ", "_"),
                                                             person["avatar"],
                                                             x + x_offset * AVATAR_WIDTH_HEIGHT,
                                                             y + y_offset * AVATAR_WIDTH_HEIGHT, AVATAR_WIDTH_HEIGHT))
                    x_offset += 1

        office_svg = office_svg.replace("</svg>", '</br>'.join(people_mappings) + '</svg>')
        return office_svg


def get_dashboard_parameters():
    slave_ids = list(set([str(m.slave_id) for det in Detection.query.all() for m in det.measurements.all()]))
    canvases = ['<table class="table"><thead><th>Current Measurements - Slave ' + slave_id + '</th></thead></table><canvas id="chart-' + slave_id + '" width="1000" height="300"></canvas></br>' for slave_id in slave_ids]
    return slave_ids, canvases


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
    mac = get_mac_from_request(request)
    user = User.query.filter_by(email=current_user.email).first()
    if mac is not None and not Device.query.filter_by(user=user, mac=mac).first():
        ask_for_adding = True
    return render_template('index.html', **get_context(ask_for_adding=ask_for_adding, mac=mac, email=user.email))


@app.route('/add_device', methods=['POST'])
def add_device():
    if current_user.is_anonymous:
        return "Sorry but you must be logged in to add devices."
    mac = request.form['mac']
    email = request.form['email']
    user = User.query.filter_by(email=email).first()
    if not Device.query.filter_by(user=user, mac=mac).first():
        db.session.add(Device(mac=mac, user=user))
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/training')
@login_required
@is_employee
def training():
    ask_for_adding = False
    client_mac = get_mac_from_request(request)
    if client_mac is not None:
        client_mac = client_mac.upper()
    current_location = 'Not known, yet'
    locations = [l.value for l in Location.query.all()]
    training_macs = [t.mac for t in TrainingDetection.query.group_by('mac').all()]
    current_detected_macs = [d.mac for d in Detection.query.filter_by(type='detection').all()]
    champions, training_json = get_training_table(training_macs, locations)
    slave_ids, canvases = get_dashboard_parameters()

    if client_mac in current_detected_macs:
        ask_for_adding = True
        try:
            df = get_df_from_detection([Detection.query.filter_by(type='detection', mac=client_mac).first()])
            current_location = predict_location(df)["predicted_location"][0]
        except Exception, e:
            traceback.print_exc(file=sys.stdout)
            print e
    return render_template('training.html', **get_context(champions=champions,
                           training_json=training_json,
                           ask_for_adding=ask_for_adding,
                           locations=locations, mac=client_mac,
                           current_location=current_location,
                           slave_ids=slave_ids, canvases=canvases))


@app.route('/current_locations')
@login_required
@is_employee
def current_locations():
    return json.dumps(get_current_locations())


@app.route('/dashboard')
@login_required
@is_employee
def dashboard():
    slave_ids = list(set([str(m.slave_id) for det in Detection.query.all() for m in det.measurements.all()]))
    canvases = ['<table class="table"><thead><th>Current Measurements - Slave ' + slave_id + '</th></thead></table><canvas id="chart-' + slave_id + '" width="1000" height="300"></canvas></br>' for slave_id in slave_ids]
    return render_template('dashboard.html', **get_context(slave_ids=slave_ids, canvases=canvases))


@app.route('/test_mapping')
@login_required
@is_employee
def test_mapping():
    with open("static/office.svg") as f:
        office_svg = f.read()
    return render_template('test_mapping.html', **get_context(office_svg=office_svg))


@app.route('/office_map')
@login_required
@is_employee
def office():
    return get_office_map_with_persons()


def get_image_for_map(id, avatar_url, x, y, width_height):
    cx = x + width_height / 2
    cy = y + width_height / 2
    radius = width_height / 2

    content = "<clipPath id='{}'>".format(id)
    content += '<circle cx="%(cx)s" cy="%(cy)s" r="%(radius)s" />' % locals()
    content += '</clipPath>'
    content += '<image x="%(x)s" y="%(y)s" xlink:href="%(avatar_url)s" height="%(width_height)s" width="%(width_height)s" clip-path="url(#%(id)s)"></image>' % locals()
    return content


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


@app.route("/training_plot_macs.png")
def training_plot_macs():
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


@app.route("/training_plot.png")
def training_plot():
    # Render image in another process to avoid segmentation fault
    import subprocess
    process = subprocess.Popen(['python', '-c', 'from master import get_training_image; get_training_image()'], stdout=subprocess.PIPE)
    out, err = process.communicate()
    response = make_response(out)
    response.headers['Content-Type'] = 'image/png'
    return response


def get_training_image():
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure
    import seaborn as sns
    import StringIO

    fig = Figure()
    df = pd.DataFrame.from_dict(get_flattened_training_data())
    features = [f for f in df.columns if f not in ['mac', 'location']]
    df = df.rename(columns=dict(zip(features, [POWER_SLAVE_PREFIX + f for f in features])))

    sns_plot = sns.pairplot(df, hue="location", vars=[POWER_SLAVE_PREFIX + f for f in features])
    png_output = StringIO.StringIO()
    sns_plot.savefig(png_output, format='png')

    canvas = FigureCanvas(fig)
    canvas.print_png(png_output)
    print png_output.getvalue()
    return


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
    db.session.commit()
    return "Updated measurement of " + str(len(data)) + " entries"


@app.route('/add_training', methods=['POST'])
def add_training():
    if current_user.is_anonymous:
        return "Sorry but you must be logged in to add training data."
    mac = request.form['mac']
    location = request.form['location']
    current_detection = Detection.query.filter_by(type='detection', mac=mac).first()
    training_detection = TrainingDetection(location=Location.query.filter_by(value=location).first(), mac=mac)
    db.session.add(training_detection)
    for m in current_detection.measurements:
        power = m.power
        if measurement_too_old(m):
            power = -100
        measurement = Measurement(m.slave_id, power, datetime.datetime.now(), training_detection)
        db.session.add(measurement)
    db.session.commit()
    user = User.query.filter_by(email=current_user.email).first()
    if not Device.query.filter_by(user=user, mac=mac).first():
        db.session.add(Device(mac=mac, user=user))
        db.session.commit()
    training_data = get_flattened_training_data()
    if len(training_data) > 0:
        train_models(training_data)
    return redirect(url_for('training'))


if __name__ == "__main__":
    generate_tls_certificate = os.environ.get("GENERATE_TLS_CERTIFICATE", True)
    tls_params = {}
    if generate_tls_certificate:
        """ SSL is required to use Google OAuth."""
        from werkzeug.serving import make_ssl_devcert
        if not os.path.isfile('ssl.crt') and not os.path.isfile('ssl.key'):
            make_ssl_devcert('./ssl', host='localhost')
        tls_params["ssl_context"] = ('./ssl.crt', './ssl.key')
    schedule.every().day.do(remove_old_detections)
    app.run(debug=False, host='0.0.0.0', threaded=True, **tls_params)
