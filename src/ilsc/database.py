# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

__all__ = [
    # global objects
    'appDatabase',
    # classes
    'User',
    'DBGuest',
    'DBCheckin',
    'DBOrganisations',
    'DBLocations',
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

appDatabase = SQLAlchemy()

class ILSCMeta(appDatabase.Model):
    '''
    metadata
    '''
    __tablename__ = 'meta_data'
    # Columns
    id = appDatabase.Column(appDatabase.Integer, primary_key=True)
    version = appDatabase.Column(appDatabase.Text(16))
    created = appDatabase.Column(appDatabase.DateTime)
    ##
    # Public methods
    ##
    def __init__(self):
        self.version = '0.4'
        self.created = datetime.utcnow()
    def __repr__(self):
        return '<ILSCMeta %r>' % (self.version)

class User(appDatabase.Model, flask_login.UserMixin):
    '''
    user database
    '''
    __tablename__ = 'user'
    # Columns
    id = appDatabase.Column(appDatabase.Integer, primary_key=True)
    userid = appDatabase.Column(appDatabase.String(128))
    username = appDatabase.Column(appDatabase.String(32), unique=True)
    devision = appDatabase.Column(appDatabase.Integer, default = 0)
    isadmin = appDatabase.Column(appDatabase.Boolean, default = False)
    salt = appDatabase.Column(appDatabase.String(32))
    password = appDatabase.Column(appDatabase.String(128))
    created = appDatabase.Column(appDatabase.DateTime)
    active = appDatabase.Column(appDatabase.Boolean)
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

class DBGuest(appDatabase.Model):
    '''
    guest database
    '''
    __tablename__ = 'tbl_guests'
    __usage__ = 'DBGuest'
    # Columns
    id = appDatabase.Column(appDatabase.Integer, primary_key=True)
    created = appDatabase.Column(appDatabase.DateTime, default=datetime.now)#, onupdate=datetime.now)
    fname = appDatabase.Column(appDatabase.LargeBinary)
    sname = appDatabase.Column(appDatabase.LargeBinary)
    contact = appDatabase.Column(appDatabase.LargeBinary)
    guid = appDatabase.Column(appDatabase.VARCHAR(255))
    agreed = appDatabase.Column(appDatabase.Boolean())
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

class DBCheckin(appDatabase.Model):
    '''
    checkin/out datatable
    '''
    __tablename__ = 'tbl_checkins'
    __usage__ = 'DBCheckins'
    # Columns
    id = appDatabase.Column(appDatabase.Integer, primary_key=True)
    guid = appDatabase.Column(appDatabase.VARCHAR(255))
    checkin = appDatabase.Column(appDatabase.DateTime, default=datetime.now)
    checkout = appDatabase.Column(appDatabase.DateTime, default=None )
    devision = appDatabase.Column(appDatabase.Integer, default=0)
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

class DBOrganisations(appDatabase.Model):
    '''
    Organisations databse
    '''
    __tablename__ = 'tbl_organisations'
    __usage__ = 'Organisations'
    # Columns
    id = appDatabase.Column(appDatabase.Integer, primary_key=True)
    name = appDatabase.Column(appDatabase.VARCHAR(255))

    ##
    # Public methods
    ##
    def __init__(self, name, oid = None):
        try:
            self.id = oid #Primary Key
            self.name = name

        except Exception as e:
            print(e)

        
    def __repr__(self):
        return f'<Organisation {self.guid}>'
    
    def json_serialize(self,*args):
        for a in args:
            sdict = self.__dict__
            if a in sdict:
                del sdict[a]
        return sdict
    
    def entitytype(self):
        return __name__

class DBLocations(appDatabase.Model):
    '''
    Locations databse
    '''
    __tablename__ = 'tbl_locations'
    __usage__ = 'Locations'
    # Columns
    id = appDatabase.Column(appDatabase.Integer, primary_key=True)
    name = appDatabase.Column(appDatabase.VARCHAR(255))
    organisation = appDatabase.Column(appDatabase.Integer, default=0)
    ##
    # Public methods
    ##
    def __init__(self, name, organisation=0, lid = None):
        try:
            self.id = lid #Primary Key
            self.name = name
            self.organisation = organisation

        except Exception as e:
            print(e)

        
    def __repr__(self):
        return f'<Location {self.lid}>'
    
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
        appDatabase.drop_all()
        appDatabase.create_all()
    
        # add meta
        meta = ILSCMeta()
        appDatabase.session.add(meta)
        appDatabase.session.commit()

        dauser = User(username='admin',
                        password='admin',
                        devision = 0,
                        isadmin = True,
                        do_hash=True)
        appDatabase.session.add(dauser)
        appDatabase.session.commit()

        organisation = DBOrganisations(oid = 0,
                            name='Mainorganisation')
        appDatabase.session.add(organisation)
        appDatabase.session.commit()

        organisation = DBLocations(lid = 0,
                            name='Mainlocation',
                            organisation = 0)
        appDatabase.session.add(organisation)
        appDatabase.session.commit()

    except Exception as e:
        print(e)
