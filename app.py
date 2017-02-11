from dotenv import load_dotenv, find_dotenv
from flask import Flask, request, redirect, url_for, session, render_template
from flask_login import LoginManager, login_user, logout_user, current_user, \
                        login_required
from flask_sslify import SSLify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from models import get_models
from requests_oauthlib import OAuth2Session
import json
import os

load_dotenv(find_dotenv())
COMPANY_EMAIL = "@futurice.com"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.getcwd() + '/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
sslify = SSLify(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"
User, Location, Detection, TrainingDetection, Measurement = get_models(db)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


""" OAuth Session creation """


def get_google_auth(state=None, token=None):
    if token:
        return OAuth2Session(Auth.CLIENT_ID, token=token)
    if state:
        return OAuth2Session(
            Auth.CLIENT_ID,
            state=state,
            redirect_uri=Auth.REDIRECT_URI)
    oauth = OAuth2Session(
        Auth.CLIENT_ID,
        redirect_uri=Auth.REDIRECT_URI,
        scope=Auth.SCOPE)
    return oauth


""" App Routing """


def is_employee(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.email.endswith(COMPANY_EMAIL):
            return f(*args, **kwargs)
        else:
            return render_template('denied.html')
    return decorated_function


class Auth:
    """Google Project Credentials"""
    CLIENT_ID = os.environ.get('CLIENT_ID', None)
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET', None)
    HOST = os.environ.get('HOST', 'localhost:5000')
    REDIRECT_URI = 'https://{host}/gCallback'.format(host=HOST)
    AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
    TOKEN_URI = 'https://accounts.google.com/o/oauth2/token'
    USER_INFO = 'https://www.googleapis.com/userinfo/v2/me'
    SCOPE = ['email']


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    google = get_google_auth()
    auth_url, state = google.authorization_url(
        Auth.AUTH_URI, access_type='offline')
    session['oauth_state'] = state
    return render_template('login.html', auth_url=auth_url)


@app.route('/gCallback')
def callback():
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('index'))
    if 'error' in request.args:
        if request.args.get('error') == 'access_denied':
            return 'You denied access.'
        return 'Error encountered.'
    if 'code' not in request.args and 'state' not in request.args:
        return redirect(url_for('login'))
    else:
        google = get_google_auth(state=session['oauth_state'])
        try:
            token = google.fetch_token(
                Auth.TOKEN_URI,
                client_secret=Auth.CLIENT_SECRET,
                authorization_response=request.url.replace("http://", "https://"))
        except HTTPError:
            return 'HTTPError occurred.'
        google = get_google_auth(token=token)
        resp = google.get(Auth.USER_INFO)
        if resp.status_code == 200:
            user_data = resp.json()
            email = user_data['email']
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User()
                user.email = email
            user.name = user_data['name']
            user.tokens = json.dumps(token)
            user.avatar = user_data['picture']
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
        return 'Could not fetch your information.'


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
