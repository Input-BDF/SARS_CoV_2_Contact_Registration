# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

__all__ = [
    # global objects
    'gDatabase',
    # classes
    'User',
    'DBGuest',
    'DBCheckin',
    # methods
    'check_database',
    'init_database'
]
import uuid, hashlib
#import flask_sqlalchemy
import flask_login
from sqlalchemy_utils import database_exists
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

gDatabase = SQLAlchemy()

class ILSCMeta(gDatabase.Model):
    '''
    metadata
    '''
    __tablename__ = 'meta_data'
    # Columns
    id = gDatabase.Column(gDatabase.Integer, primary_key=True)
    version = gDatabase.Column(gDatabase.Text(16))
    created = gDatabase.Column(gDatabase.DateTime)
    ##
    # Public methods
    ##
    def __init__(self):
        self.version = '0.4'
        self.created = datetime.utcnow()
    def __repr__(self):
        return '<ILSCMeta %r>' % (self.version)

class User(gDatabase.Model, flask_login.UserMixin):
    '''
    user database
    '''
    __tablename__ = 'user'
    # Columns
    id = gDatabase.Column(gDatabase.Integer, primary_key=True)
    userid = gDatabase.Column(gDatabase.String(128))
    username = gDatabase.Column(gDatabase.String(32), unique=True)
    devision = gDatabase.Column(gDatabase.Integer, default = 0)
    isadmin = gDatabase.Column(gDatabase.Boolean, default = False)
    salt = gDatabase.Column(gDatabase.String(32))
    password = gDatabase.Column(gDatabase.String(128))
    created = gDatabase.Column(gDatabase.DateTime)
    active = gDatabase.Column(gDatabase.Boolean)
    ##
    # Public methods
    ##
    def __init__(self, username, password, devision=0, salt=None, isadmin = False, do_hash=True):
        self.salt = salt if salt else self.__salt()
        self.set_username(username)
        self.set_password(password, do_hash)
        self.devision=devision
        self.isadmin = isadmin
        self.created = datetime.utcnow()
        self.active = True
    def __repr__(self):
        return '<User %r>' % (self.username)
    def __call__(self):
        return {
            'username': self.username,
            'created': self.created,
            'active': self.active
        }
    def set_username(self, username):
        self.username = username
        self.userid = self.__hash(username.encode('utf-8'), self.salt.encode('utf-8'))
    def set_password(self, password, do_hash=True):
        self.password = password if not do_hash else self.__hash(password.encode('utf-8'), self.salt.encode('utf-8'))
    def validate_password(self, password):
        return (self.password == self.__hash(password.encode('utf-8'), self.salt.encode('utf-8')))
    ##
    # Override UserMixin
    ##
    def get_id(self):
        return self.userid
    ##
    # Private methods
    ##
    @staticmethod
    def __salt():
        return uuid.uuid4().hex
    @staticmethod
    def __hash(string, salt):
        return hashlib.sha512(string + salt).hexdigest()

class DBGuest(gDatabase.Model):
    '''
    guest database
    '''
    __tablename__ = 'tbl_guests'
    __usage__ = 'DBGuest'
    # Columns
    id = gDatabase.Column(gDatabase.Integer, primary_key=True)
    created = gDatabase.Column(gDatabase.DateTime, default=datetime.now)#, onupdate=datetime.now)
    fname = gDatabase.Column(gDatabase.LargeBinary)
    sname = gDatabase.Column(gDatabase.LargeBinary)
    contact = gDatabase.Column(gDatabase.LargeBinary)
    guid = gDatabase.Column(gDatabase.VARCHAR(255))
    agreed = gDatabase.Column(gDatabase.Boolean())
    ##
    # Public methods
    ##
    def __init__(self, fname, sname, contact, guid, agreed, gid = None):
        try:
            self.id = gid #Primary Key
            self.fname = fname
            self.sname = sname
            self.contact = contact
            self.guid = guid
            self.agreed = agreed
        except Exception as e:
            print(e)

        
    def __repr__(self):
        return '<Guest %s>' % (self.guid)
    
    def json_serialize(self,*args):
        for a in args:
            sdict = self.__dict__
            if a in sdict:
                del sdict[a]
        return sdict
    
    def entitytype(self):
        return __name__

class DBCheckin(gDatabase.Model):
    '''
    checkin/out datatable
    '''
    __tablename__ = 'tbl_checkins'
    __usage__ = 'DBCheckins'
    # Columns
    id = gDatabase.Column(gDatabase.Integer, primary_key=True)
    guid = gDatabase.Column(gDatabase.VARCHAR(255))
    checkin = gDatabase.Column(gDatabase.DateTime, default=datetime.now)
    checkout = gDatabase.Column(gDatabase.DateTime, default=None )
    devision = gDatabase.Column(gDatabase.Integer, default=0)
    ##
    # Public methods
    ##
    def __init__(self, guid, gid = None, devision = 0):
        try:
            self.id = gid #Primary Key
            self.guid = guid
            self.devision = devision

        except Exception as e:
            print(e)

        
    def __repr__(self):
        return '<Checkin %s>' % (self.guid)
    
    def json_serialize(self,*args):
        for a in args:
            sdict = self.__dict__
            if a in sdict:
                del sdict[a]
        return sdict
    
    def entitytype(self):
        return __name__
##
# Database initialization
##
def check_database(uri):
    '''
    check if database already exists
    '''
    if database_exists(uri):
        try:
            meta = ILSCMeta.query.first()
            if meta and meta.version:
                return True
        except Exception as e:
            print(e)
    return False

def init_database():
    '''
    initialize database and primary user
    '''
    try:
        gDatabase.drop_all()
        gDatabase.create_all()
    
        # add meta
        meta = ILSCMeta()
        gDatabase.session.add(meta)
        gDatabase.session.commit()

        dauser = User(username='admin',
                        password='admin',
                        devision = 0,
                        isadmin = True,
                        do_hash=True)
        gDatabase.session.add(dauser)
        gDatabase.session.commit()

    except Exception as e:
        print(e)
