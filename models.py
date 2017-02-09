from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import os
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.getcwd() + '/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(50), unique=True)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return '<Location %r>' % (self.value)

    def serialize(self):
        return { 'value': self.value }


class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime)

    def __init__(self, mac):
        self.mac = mac
        self.last_updated = datetime.datetime.now()

    def __repr__(self):
        return '<Detection %r (%r)>' % (self.mac, str(self.last_updated))

    def serialize(self):
        return { 'mac':self.mac }


class TrainingDetection(Detection):
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    location = db.relationship('Location', backref=db.backref('training_detections', lazy='dynamic'))

    def __init__(self, mac, location):
        self.mac = mac
        self.last_updated = datetime.datetime.now()
        self.location = location

    def __repr__(self):
        return '<TrainingDetection at %r for %r (%r)>' % (self.location, self.mac, str(self.last_updated))

    def serialize(self):
        return { 'mac':self.mac, 'location': self.location.serialize() }


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

    def serialize(self):
        return { 'power': self.power, 'slave_id': self.slave_id }
