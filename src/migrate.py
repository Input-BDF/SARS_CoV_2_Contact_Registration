'''
Created on 13.06.2020

@author: Input
'''
'''
usage:
*init db
python3 migrate.py db init
python3 migrate.py db migrate
*make changes
python3 migrate.py db migrate
python3 upgrade
'''

from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
import flask_login

from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

app = Flask(__name__)
app.config.from_pyfile('migrate.cfg')

naming_convention = {
        "ix": 'ix_%(column_0_label)s',
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }

appDB = SQLAlchemy(app = app, metadata=MetaData(naming_convention=naming_convention))

migrate = Migrate(app, appDB, render_as_batch=True)
manager = Manager(app)

manager.add_command('db', MigrateCommand)

class ILSCMeta(appDB.Model):
    '''
    metadata
    '''
    __tablename__ = 'meta_data'
    id = appDB.Column(appDB.Integer, primary_key=True)
    version = appDB.Column(appDB.Text(16))
    created = appDB.Column(appDB.DateTime)

class User(appDB.Model, flask_login.UserMixin):
    __tablename__ = 'user'
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

class Roles(appDB.Model):
    __tablename__ = 'roles'
    id = appDB.Column(appDB.Integer(), primary_key=True)
    name = appDB.Column(appDB.String(50), unique=True)

class UserRoles(appDB.Model):
    __tablename__ = 'user_roles'
    id = appDB.Column(appDB.Integer(), primary_key=True)
    user_id = appDB.Column(appDB.Integer(), appDB.ForeignKey('user.id', ondelete='CASCADE'))
    role_id = appDB.Column(appDB.Integer(), appDB.ForeignKey('roles.id', ondelete='CASCADE'))

class DBGuest(appDB.Model):
    __tablename__ = 'tbl_guests'
    __usage__ = 'DBGuest'
    id = appDB.Column(appDB.Integer, primary_key=True)
    created = appDB.Column(appDB.DateTime, default=datetime.now)#, onupdate=datetime.now)
    fname = appDB.Column(appDB.LargeBinary)
    sname = appDB.Column(appDB.LargeBinary)
    contact = appDB.Column(appDB.LargeBinary)
    guid = appDB.Column(appDB.VARCHAR(255))
    agreed = appDB.Column(appDB.Boolean())

class DBCheckin(appDB.Model):
    __tablename__ = 'tbl_checkins'
    __usage__ = 'DBCheckins'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    guid = appDB.Column(appDB.VARCHAR(255))
    checkin = appDB.Column(appDB.DateTime, default=datetime.now)
    checkout = appDB.Column(appDB.DateTime, default=None )
    devision = appDB.Column(appDB.Integer, default=0)

class DBOrganisations(appDB.Model):
    __tablename__ = 'tbl_organisations'
    __usage__ = 'Organisations'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    name = appDB.Column(appDB.VARCHAR(255), unique=True)
    locations = appDB.relationship('DBLocations')

class DBLocations(appDB.Model):
    __tablename__ = 'tbl_locations'
    __usage__ = 'Locations'
    # Columns
    id = appDB.Column(appDB.Integer, primary_key=True)
    name = appDB.Column(appDB.VARCHAR(255))
    organisation = appDB.Column(appDB.Integer(), appDB.ForeignKey('tbl_organisations.id', ondelete='CASCADE'))
    checkouts = appDB.Column(appDB.VARCHAR(255))

def reinit_database():
    '''
    initialize database and primary user
    '''
    try:
        '''
        appDB.drop_all()
        appDB.create_all()
        '''
        '''
        # add meta
        meta = ILSCMeta()
        appDB.session.add(meta)
        appDB.session.commit()
        '''

        super_role = Roles(name='SuperUser')
        visit_role = Roles(name='VisitorAdmin')
        admin_role = Roles(name='UserAdmin')
        location_role = Roles(name='LocationAdmin')
        appDB.session.commit()

        newadmin = User(username='admin',
                        password='admin',
                        devision = 0,
                        do_hash=True)

        newadmin.roles = [super_role, visit_role, admin_role, location_role]

        appDB.session.add(newadmin)
        appDB.session.commit()

        organisation = DBOrganisations(oid = 0,
                            name='Mainorganisation')
        appDB.session.add(organisation)
        appDB.session.commit()

        location = DBLocations(lid = 0,
                            name='Mainlocation',
                            organisation = 0)
        appDB.session.add(location)
        appDB.session.commit() 

    except Exception as e:
        print(e)

if __name__ == '__main__':
    try:
        manager.run()
        reinit_database()
    except Exception as e:
        print(e)