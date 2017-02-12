""" DB Models """

import datetime
from flask_login import UserMixin

models = None


def init_models(db):
    global models
    if not models:
        class User(db.Model, UserMixin):
            __tablename__ = "users"
            id = db.Column(db.Integer, primary_key=True)
            email = db.Column(db.String(100), unique=True, nullable=False)
            avatar = db.Column(db.String(200))
            tokens = db.Column(db.Text)

            def __repr__(self):
                return '<User %r>' % (self.email)

            def serialize(self):
                serialized = { 'email': self.email }
                for d in self.devices:
                    serialized['devices'].append(d.serialize())
                return serialized

        class Device(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            mac = db.Column(db.String(50), unique=True, nullable=False)
            user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
            user = db.relationship('User', backref=db.backref('devices', lazy='dynamic'))

            def __init__(self, mac, user):
                self.mac = mac
                self.user = user

            def __repr__(self):
                return '<Device %r>' % (self.mac)

            def serialize(self):
                return { 'mac': self.mac }


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
            __tablename__ = 'detection'
            id = db.Column(db.Integer, primary_key=True)
            type = db.Column(db.String(20))
            mac = db.Column(db.String(50))
            last_updated = db.Column(db.DateTime)

            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity':'detection',
                'with_polymorphic':'*'
            }

            def __init__(self, mac):
                self.mac = mac
                self.last_updated = datetime.datetime.now()

            def __repr__(self):
                return '<Detection %r (%r)>' % (self.mac, str(self.last_updated))

            def serialize(self):
                serialized = { 'mac':self.mac , 'measurements': []}
                for m in self.measurements:
                    serialized['measurements'].append(m.serialize())
                return serialized



        class TrainingDetection(Detection):
            __tablename__ = 'training_detection'
            id = db.Column(db.Integer, db.ForeignKey('detection.id'), primary_key=True)
            location_id = db.Column(db.Integer, db.ForeignKey('location.id'))
            location = db.relationship('Location', backref=db.backref('training_detections', lazy='dynamic'))

            __mapper_args__ = {
                    'polymorphic_identity':'training_detection',
                }

            def __init__(self, mac, location):
                self.mac = mac
                self.last_updated = datetime.datetime.now()
                self.location = location

            def __repr__(self):
                return '<TrainingDetection at %r for %r (%r)>' % (self.location, self.mac, str(self.last_updated))

            def serialize(self):
                serialized = { 'mac':self.mac, 'location': self.location.serialize(), 'measurements': []}
                for m in self.measurements:
                    serialized['measurements'].append(m.serialize())
                return serialized


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
        models = (User, Location, Detection, TrainingDetection, Measurement)
    return


def get_models(db):
    global models
    init_models(db)
    return models
