# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

__all__ = [
    # global objects
    'appDB',
    # classes
    'User',
    'Roles',
    'UserRoles',
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
from sqlalchemy import func

appDB = SQLAlchemy()

class ILSCMeta(appDB.Model):
    '''
    metadata
    '''
    __tablename__ = 'meta_data'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    version = appDB.Column(appDB.Text(16))
    created = appDB.Column(appDB.DateTime)
    ##
    # Public methods
    ##
    def __init__(self):
        self.version = '0.5'
        self.created = datetime.utcnow()
    def __repr__(self):
        return '<ILSCMeta %r>' % (self.version)

class User(appDB.Model, flask_login.UserMixin):
    '''
    user database
    '''
    __tablename__ = 'user'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    userid = appDB.Column(appDB.String(128))
    username = appDB.Column(appDB.String(32), unique=True)
    devision = appDB.Column(appDB.Integer(), appDB.ForeignKey('tbl_locations.id', ondelete='CASCADE'))
    salt = appDB.Column(appDB.String(32))
    password = appDB.Column(appDB.String(128))
    created = appDB.Column(appDB.DateTime)
    active = appDB.Column(appDB.Boolean)
    
    roles = appDB.relationship('Roles', secondary='user_roles',
                                lazy='subquery',
                                backref=appDB.backref('user', lazy='dynamic'))
    
    location = appDB.relationship('DBLocations', foreign_keys=devision, post_update=True, lazy='subquery')
    ##
    # Public methods
    ##
    def __init__(self, username, password, devision=0, salt=None, do_hash=True):
        self.salt = salt if salt else self.__salt()
        self.set_username(username)
        self.set_password(password, do_hash)
        self.devision=devision
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
    
    def get_roles(self, exclude = -1):
        return { ur.id : ur.name for ur in self.roles if ur != exclude }

    def set_roles(self):
        pass

    def is_admin(self):
        return bool(self.get_roles())

    def is_superuser(self):
        return 1 in self.get_roles().keys()
    ##
    # Override UserMixin
    ##
    def get_id(self):
        return self.userid
    
    @staticmethod
    def check_duplicate(needle):
        _result = appDB.session.query(User).filter(func.lower(User.username) == func.lower(needle)).first()
        if _result: return True
        else: return False
    ##
    # Private methods
    ##
    @staticmethod
    def __salt():
        return uuid.uuid4().hex
    @staticmethod
    def __hash(string, salt):
        return hashlib.sha512(string + salt).hexdigest()

class Roles(appDB.Model):
    '''
    Define the Role data-model
    '''
    __tablename__ = 'roles'
    id = appDB.Column(appDB.Integer(), primary_key=True)
    name = appDB.Column(appDB.String(50), unique=True)

    @staticmethod
    def get_roles():
        return appDB.session.query(Roles).order_by(Roles.id).all()

    @staticmethod
    def get_roles_pairs(exclude = -1):
        return [(r.id, r.name) for r in Roles.get_roles() if r.id != exclude]

    @staticmethod
    def get_roles_by_ids(ids):
        if ids:
            roles = appDB.session.query(Roles).filter(Roles.id.in_(ids)).order_by(Roles.id).all()
            if roles: return roles
        return []

class UserRoles(appDB.Model):
    '''
    Define the UserRoles association table
    '''
    __tablename__ = 'user_roles'
    id = appDB.Column(appDB.Integer(), primary_key=True)
    user_id = appDB.Column(appDB.Integer(), appDB.ForeignKey('user.id', ondelete='CASCADE'))
    role_id = appDB.Column(appDB.Integer(), appDB.ForeignKey('roles.id', ondelete='CASCADE'))

class DBGuest(appDB.Model):
    '''
    guest database
    '''
    __tablename__ = 'tbl_guests'
    __usage__ = 'DBGuest'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    created = appDB.Column(appDB.DateTime, default=datetime.now)#, onupdate=datetime.now)
    fname = appDB.Column(appDB.LargeBinary)
    sname = appDB.Column(appDB.LargeBinary)
    contact = appDB.Column(appDB.LargeBinary)
    guid = appDB.Column(appDB.VARCHAR(255))
    agreed = appDB.Column(appDB.Boolean())
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

class DBCheckin(appDB.Model):
    '''
    checkin/out datatable
    '''
    __tablename__ = 'tbl_checkins'
    __usage__ = 'DBCheckins'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    guid = appDB.Column(appDB.VARCHAR(255))
    checkin = appDB.Column(appDB.DateTime, default=datetime.now)
    checkout = appDB.Column(appDB.DateTime, default=None )
    devision = appDB.Column(appDB.Integer, default=0)
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

class DBOrganisations(appDB.Model):
    '''
    Organisations databse
    '''
    __tablename__ = 'tbl_organisations'
    __usage__ = 'Organisations'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    name = appDB.Column(appDB.VARCHAR(255), unique=True)

    locations = appDB.relationship('DBLocations')
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
        return f'<Organisation {self.id}>'
    
    def json_serialize(self,*args):
        for a in args:
            sdict = self.__dict__
            if a in sdict:
                del sdict[a]
        return sdict
    
    def entitytype(self):
        return __name__

    @staticmethod
    def check_duplicate(needle):
        _result = appDB.session.query(DBOrganisations).filter(func.lower(DBOrganisations.name) == func.lower(needle)).first()
        if _result: return True
        else: return False

class DBLocations(appDB.Model):
    '''
    Locations databse
    '''
    __tablename__ = 'tbl_locations'
    __usage__ = 'Locations'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    name = appDB.Column(appDB.VARCHAR(255))
    organisation = appDB.Column(appDB.Integer(), appDB.ForeignKey('tbl_organisations.id', ondelete='CASCADE'))
    checkouts = appDB.Column(appDB.VARCHAR(255))
    ##
    # Public methods
    ##
    def __init__(self, name, organisation=0, checkouts=None, lid = None):
        try:
            self.id = lid #Primary Key
            self.name = name
            self.organisation = organisation
            self.checkouts = checkouts

        except Exception as e:
            print(e)

    def __repr__(self):
        return f'<Location {self.id}>'
    
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
        appDB.drop_all()
        appDB.create_all()

        # add meta
        meta = ILSCMeta()
        appDB.session.add(meta)
        appDB.session.commit()

        super_role = Roles(name='SuperUser')
        visit_role = Roles(name='VisitorAdmin')
        admin_role = Roles(name='UserAdmin')
        location_role = Roles(name='LocationAdmin')
        appDB.session.commit()

        firstuser = User(username='admin',
                        password='admin',
                        devision = 0,
                        do_hash=True)

        firstuser.roles = [super_role, visit_role, admin_role, location_role]

        appDB.session.add(firstuser)
        appDB.session.commit()

        organisation = DBOrganisations(oid = 0,
                            name='Mainorganisation')
        appDB.session.add(organisation)
        appDB.session.commit()

        location = DBLocations(lid = 0,
                            name='Mainlocation',
                            organisation = 0, checkouts=0)
        appDB.session.add(location)
        appDB.session.commit()

    except Exception as e:
        print(e)
