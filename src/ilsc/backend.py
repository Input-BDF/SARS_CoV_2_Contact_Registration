# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''
from sqlalchemy.engine import strategies

__all__ = ['Backend']

import flask
import json
import logging
import os
import pyqrcode
import uuid
import zlib
from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from werkzeug.http import parse_date
from flask import Markup
from flask_login import current_user
from itsdangerous import base64_decode
from autobahn.twisted.resource import WebSocketResource, Resource
from .websocket import *
from twisted.web.server import Site
from sqlalchemy import and_, or_, between
from sqlalchemy import exc

from ilsc.database import DBGuest, DBCheckin, User, DBOrganisations, DBLocations, Roles, ILSCMeta, DBDeleteProtocol
from ilsc import caesar

from bs4 import BeautifulSoup

def clean_strings(string):
    '''
    sanitize string and remove not wanted stuff
    '''
    try:
        soup = BeautifulSoup(string, 'html.parser') # create a new bs4 object from the html data loaded
        for script in soup(["script", "style"]): # remove all javascript and stylesheet code
            script.extract()
        # get text
        text = soup.get_text()
        # break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        text = text.encode('ascii', 'xmlcharrefreplace').strip()
        return text
    except Exception as e:
        print('Clean_Strings', e)

def flask_loads(value):
    #TODO: maybe i don't relly need this
    """Flask uses a custom JSON serializer so they can encode other data types.
    This code is based on theirs, but we cast everything to strings because we
    don't need them to survive a roundtrip if we're just decoding them."""
    def object_hook(obj):
        if len(obj) != 1:
            return obj
        the_key, the_value = next(obj.iteritems())
        if the_key == ' t':
            return str(tuple(the_value))
        elif the_key == ' u':
            return str(uuid.UUID(the_value))
        elif the_key == ' b':
            return str(b64decode(the_value))
        elif the_key == ' m':
            return str(Markup(the_value))
        elif the_key == ' d':
            return str(parse_date(the_value))
        return obj
    return json.loads(value, object_hook=object_hook)

class visit():
    '''
    class for better guest returning
    '''
    def __init__(self, guid, checkin, checkout, day, devision):
        self.guid = guid
        self.checkin = checkin
        self.checkout = checkout
        self.devision = devision
        self.day = day

class decoded_guest():
    '''
    class for better guest returning
    '''
    def __init__(self, guid, fname, sname, contact, checkin, checkout, devision):
        self.guid = guid
        self.fname = fname
        self.sname = sname
        self.contact = contact
        self.checkin = checkin
        self.checkout = checkout
        self.devision = devision

class Backend(object):
    '''Backend class'''
    def __init__(self, config, flaskApp, appDB, superuser, scheduler):
        '''
        Constructs a Backend object
        '''
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.appDB = appDB
        self.flaskApp = flaskApp
        self.websocket = None
        self.superuser = superuser
        self.init_websocket()
        self.scheduler = scheduler
        self.ws_token = b64encode(os.urandom(24)).decode('utf-8')

    def init_websocket(self):
        '''
        Initializes websocket
        '''
        try:
            address = u"wss://{0}:{1}".format(self.config.websocket['address'], self.config.websocket['port'])
        except:
            address = u"wss://%s:%s" % (self.config.websocket['address'], self.config.websocket['port'])
        self.websocket = WebsocketMultiServer(address)
        self.websocket.set_backend_connections(bck_end_callback=self._ws_data_callback,
                                         bck_end_connection_made=self._ws_connection_made,
                                         bck_end_connection_lost=self._ws_connection_lost,)

    def get_websocket(self):
        '''
        get_websocket
        Returns websocket
        '''
        # just return websocket
        return self.websocket
    
    def get_websocket_site(self):
        '''
        Returns websocket site
        '''
        try:
            root = Resource() #use Resource() else file system gets visible
            resource = WebSocketResource(self.websocket)
            root.putChild(b"", resource)
            site = Site(root)
            # just return websocket site
        except Exception as e:
            print(e)
        return site
    
    def _ws_data_callback(self, data, isBinary):
        '''
        Websocket data callback, base backend communication center
        '''
        try:
            _data = json.loads(data.decode('utf-8'))
            self.logger.debug(_data)
            if 'exists' in _data.keys():
                cleaned_guid = clean_strings(_data['exists'])
                _known = self.check_guid_is_checkedin(cleaned_guid, _data['devision'])
                return json.dumps({'exists': self.check_guid(cleaned_guid), 'known':_known}), isBinary
            if 'checkin' in _data.keys():
                cleaned_guid = clean_strings(_data['checkin'])
                devision = int(_data['devision'])
                success, msg = self.guest_checkin(cleaned_guid, devision)
                self._broadcast(json.dumps({
                                            'COUNTER' : self.count_guests(devision),
                                            'DEVISION' : devision
                                            }))
                return json.dumps({'checkin': success, 'msg': msg}), isBinary
            if 'checkout' in _data.keys():
                cleaned_guid = clean_strings(_data['checkout'])
                devision = int(_data['devision'])
                success, msg = self.guest_checkout(cleaned_guid, devision)
                self._broadcast(json.dumps({
                                            'COUNTER' : self.count_guests(devision),
                                            'DEVISION' : devision
                                            }))
                return json.dumps({'checkout': success, 'msg': msg}), isBinary
        except Exception as e:
            self.logger.error('Could not send data')
            self.logger.error(e)
    
    def _ws_send_callback(self, data):
        '''
        Callback function sending Websocket data
        '''
        self.websocket.send(json.dumps(data))
        pass

    def _ws_connection_made(self, cookie):
        '''
        Websocket connection made callback
        '''
        try:
            cookie_cnt = json.loads(self.decodeFlaskCookie(cookie))
            if cookie_cnt and 'wst' in cookie_cnt.keys() and cookie_cnt['wst'] == self.ws_token:
                return True
        except Exception as e:
            self.logger.warning(f'Invalid ws connection request: {e}')
        return False

    def _ws_connection_lost(self, reason):
        '''
        Websocket connection lost callback
        '''
        #self._broadcast(json.dumps({'CLIENTS' : str(len(self.websocket.clients))}))
        pass

    def _broadcast(self, payload):
        '''
        broadcast to all known clients
        '''
        self.websocket.broadcast(payload, False) 

    def _deleteEntity(self, entity, eid):
        '''
        delete DB Entry
        entity: table-entity
        eid: tables primary key value
        '''
        with self.flaskApp.app_context():
            try:
                _entity = self.appDB.session.query(entity).filter_by(id=eid).first()
                if not _entity:
                    return False
                else:
                    self.appDB.session.delete(_entity)
                    self.appDB.session.commit()
                    return True
            except Exception as e:
                self.logger.debug(e)
                return False

    def gen_guid(self, length=32):
        '''
        generate guid and return guid
        check if it's unique
        '''
        guid = uuid.uuid4().hex[:length]
        while self.check_guid(guid):
            self.gen_guid()
        return guid

    def check_guid(self, guid):
        '''
        Query Database if guid exists in guest table
        '''
        with self.flaskApp.app_context():
            try:
                c_str = clean_strings(guid)
                _guest = self.appDB.session.query(DBGuest).filter_by(guid=c_str).all()
                if not _guest:
                    #guest is totally unknown
                    return False
                else:
                    #hey i know you
                    return True
            except Exception as e:
                self.logger.debug(e)

    def check_guid_is_checkedin(self, guid, devision):
        '''
        Query Database if guid exists in checkin
        '''
        with self.flaskApp.app_context():
            try:
                c_str = clean_strings(guid)
                lookup = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkout == None,
                              DBCheckin.devision == devision)
                _query = self.appDB.session.query(DBCheckin).filter(lookup).order_by(DBCheckin.checkin.desc())
                _guest = _query.first()
                _lastaction = self.check_cooldown(guid, devision)
                if _guest:
                    #guest is checked in
                    return True
                else:
                    #guest not checked in
                    return False
            except Exception as e:
                self.logger.debug(e)

    def check_cooldown(self, guid, devision):
        '''
        Query Database if guid was useded i cooldown time
        '''
        with self.flaskApp.app_context():
            try:
                c_str = clean_strings(guid)
                #TODO: define cooldown in config
                _delta = (datetime.now() - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S.%f")

                lookup_notchecked_out = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkin < _delta,
                              DBCheckin.checkout == None,
                              DBCheckin.devision == devision)
                lookup_checked_out = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkin < _delta,
                              DBCheckin.checkout < _delta,
                              DBCheckin.devision == devision)
                '''
                lookup = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkout != 0,
                              DBCheckin.devision == devision)
                '''
                _query = self.appDB.session.query(DBCheckin).filter(or_(lookup_notchecked_out, lookup_checked_out)).order_by(DBCheckin.checkout.desc())
                _guest = _query.first()
                if _guest:
                    #guest is checked in/out within cooldown
                    return True
                else:
                    #guest is not checked in/out within cooldown
                    return False
            except Exception as e:
                self.logger.debug(e)

    def enter_guest(self, form, guid):
        '''
        enter new guest into database
        '''
        try:
            fname = clean_strings(form.firstname.data).decode('utf-8')
            sname = clean_strings(form.lastname.data).decode('utf-8')
            contact = clean_strings(form.contact.data).decode('utf-8')
            agreed = form.agree.data
            fname, sname, contact = self.encrypt_data(fname, sname, contact)
            guid = clean_strings(guid)#.decode('utf-8')
            if not self.check_guid(guid):
                if (guid != '' and fname != '' and sname != '' and contact != ''):
                    with self.flaskApp.app_context():
                        new_guest = DBGuest(fname = fname, sname = sname, contact = contact, guid = guid, agreed = agreed)
                        self.appDB.session.add(new_guest)
                        self.appDB.session.commit()
                    return True, ''
                else: return False, 'Es fehlen Werte im Formular.'
            else: return False, 'So ein Zufall. Die GUID existiert bereits. Versuchs bitte nochmal.'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Es ist ein schwerwiegender Fehler aufgetreten (x00001).'\
                          ' Versuchs bitte nochmal oder <a href="mailto:{mail}?subject=Fehler%20in%20Registerapp">'\
                          'kontaktier uns.</a>'.format(mail=self.config.app['contactmail'])

    def guest_checkin(self, guid, devision = 0):
        '''
        insert checkin into database based on guid
        '''
        try:
            guid = clean_strings(guid)
            if (not self.check_guid_is_checkedin(guid, devision)) and (self.check_guid(guid)):
                    with self.flaskApp.app_context():
                        new_guest = DBCheckin(guid = guid, devision = devision)
                        self.appDB.session.add(new_guest)
                        self.appDB.session.commit()
                    return True, 'Checkin erfolgreich'
            else: return False, 'Fehler beim Checkin'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00002) beim Checkin'

    def guest_checkout(self, guid, devision):
        '''
        Query Database if guid exists in checkin and update @ checkout time
        '''
        with self.flaskApp.app_context():
            try:
                c_str = clean_strings(guid)
                days = int(self.config.app['keepdays'])
                lookup = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkin+timedelta(days=days)<datetime.now(),
                              DBCheckin.checkout==None,
                              DBCheckin.devision == devision)
                _query = self.appDB.session.query(DBCheckin).filter(lookup).order_by(DBCheckin.checkin.desc())
                _guest = _query.first()
                if _guest:
                    _guest.checkout=datetime.now()
                    self.appDB.session.commit()
                    return True, 'Checkout erfolgreich'
                else:
                    return False, 'Da gabs nix für nen checkout.'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00002) beim Checkout. Oder der wurde grad schon ausgecheckt'

    def add_user(self, form, do_hash=True):
        '''
        add new user to database
        '''
        #TODO: User Form as passed argument
        try:
            username=form.username.data
            password=form.password.data
            if form.devision != None:
                devision = form.devision.data
            else:
                devision = form.location_id
            if form.roles != None:
                selected_roles = form.roles.data if bool(form.roles.data) else []
                selected_roles.sort()
                new_roles = Roles.get_roles_by_ids(selected_roles) 
            else:
                new_roles =  Roles.get_roles_by_ids(form.role_list)
            new_user = User(username, password, devision, do_hash=do_hash)
            new_user.roles.extend(new_roles)
            self.appDB.session.add(new_user)
            self.appDB.session.commit()
            return True, f'Nutzer "{username}" wurde angelegt'
        except exc.IntegrityError as ie:
            return False, f'Integrity-Error. Code: {ie.code}. Benutzername existiert bereits.'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Es ist ein schwerwiegender Fehler aufgetreten (x00007).'

    def update_user(self, uid, form):
        '''
        Update user data from form values based on id
        '''
        try:
            selected_roles = form.roles.data if bool(form.roles.data) else []
            selected_roles.sort()
            new_roles = Roles.get_roles_by_ids(selected_roles)

            user = self.get_user_by_id(uid=int(uid))
            user.username = clean_strings(form.username.data).decode('utf-8')
            user.devision = int(form.devision.data)

            user.roles.clear()
            user.roles.extend(new_roles)
            #TODO: keep superuser 1 the superuser
            #user.isadmin = True if user.id == self.superuser else form.isadmin.data
            #Need to check if selected roles is empty since then is_modified becomes True
            if self.appDB.session.is_modified(user):
                self.appDB.session.commit()
                return True, f'"{user.username}" erfolgreich geändert'
            return True, f'Für "{user.username}" hat sich nichts geändert.'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00005) Konnte user nicht ändern'
            
    def update_password(self, uid, form):
        '''
        Update user password from form value based on id
        '''
        try:
            user = self.get_user_by_id(uid=int(uid))
            user.set_password(form.password.data, do_hash=True)
            if self.appDB.session.is_modified(user):
                #user.password = '123456'
                self.appDB.session.commit()
                
            return True, f'Passwort für "{user.username}" erfolgreich geändert'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00005) Konnte user nicht ändern'

    def delete_user(self, uid):
        '''
        Delete user from db
        '''
        #with self.flaskApp.app_context():
        user = self.get_user_by_id(uid=int(uid))
        if user:
            self.appDB.session.delete(user)
            self.appDB.session.commit()

    def get_user_by_id(self, uid):
        '''
        Query Database for user based on id
        '''
        try:
            
            user = self.appDB.session.query(User).filter_by(id=int(uid)).first()
            if user:
                return user
            else:
                return None
        except Exception as e:
            self.logger.debug(e)
            return None

    def get_current_user(self):
        '''
        Query Database for user based on guid of active user
        '''
        if not current_user.is_authenticated: return None
        if not flask.session['_user_id']: return None
        
        try:
            user = self.appDB.session.query(User).filter_by(userid=str(flask.session['_user_id'])).first()
            if user:
                return user
            else:
                return None
        except Exception as e:
            self.logger.debug(e)

    def get_all_user_roles(self, plain = False):
        '''
        Query Database for user location based on uuid
        '''
        try:
            with self.flaskApp.app_context():
                roles = self.appDB.session.query(Roles).all()
                #self.appDB.session.close()
                if plain:
                    return roles
                if roles:
                    all_roles = { r.id : r.name for r in roles }
                    return all_roles
                else:
                    return []
        except Exception as e:
            self.logger.debug(e)
            return []

    def get_current_user_roles(self, other_user = None):
        '''
        Query Database for user location based on uuid
        '''
        try:
            user = self.get_current_user() if other_user == None else other_user
            if user:
                user_roles = { ur.id : ur.name for ur in user.roles }
                return user_roles
            else:
                return {}
        except Exception as e:
            self.logger.debug(e)
            return {}

    def check_superuser(self):
        '''
        Query Database for user location based on uuid
        '''
        try:
            user_roles = self.get_current_user().get_roles().values()
            if user_roles and "SuperUser" in user_roles:
                return True
            else:
                return False
        except Exception as e:
            self.logger.debug(e)
            return False

    def get_current_user_location(self):
        '''
        Query Database for user location based on uuid
        '''
        try:
            user = self.get_current_user()
            if user:
                return user.devision
            else:
                return None
        except Exception as e:
            self.logger.debug(e)
            return None

    def get_location_organisation(self, lid):
        '''
        return organisation associated to given location id
        '''
        oid = self.fetch_element_by_id(DBLocations, lid)
        return oid.organisation if oid else None

    def get_organisations(self):
        try:
            orgs = DBOrganisations.query.all()
            if orgs:
                all_orgs = { o.id : o.name for o in orgs }
                return all_orgs
            else:
                return []
        except Exception as e:
            self.logger.debug(e)
            return []

    def get_organisation_locations(self, orgid):
        '''
        Query Database for locations by organisation id
        '''
        with self.flaskApp.app_context():
            try:
                name = DBLocations.name.label("name")

                _query = self.appDB.session.query(DBLocations)\
                                        .filter_by(organisation=orgid)\
                                        .order_by(name)
                locations = _query.all()

                if locations:
                    ldict = {}
                    for l in locations:
                        ldict[str(l.id)] = l.name
                    
                    return locations, ldict
                else:
                    return [], {}
            except Exception as e:
                self.logger.debug(e)
                return [], {}

    def get_organisation_users(self, uid):
        '''
        Query for users belonging to current session user organisation
        '''
        try:
            _, locdict = self.get_organisation_locations(uid)
            #users = ilsc.User.query.all()
            _query = self.appDB.session.query(User).filter(User.devision.in_(locdict.keys())).order_by(User.username)
            users = _query.all()
            if users:
                return users, locdict
            else:
                return [],{}
        except Exception as e:
            self.logger.debug(e)
            return [],{}

    def check_organisation_permission(self, _test_loc):
        '''
        Check if user is allowed to access organisation infos
        '''
        with self.flaskApp.app_context():
            try:
                _user_loc = self.get_current_user_location()
                _user_org = self.get_location_organisation(_user_loc)
                _test_org = self.get_location_organisation(_test_loc)
                return _user_org == _test_org

            except Exception as e:
                self.logger.debug(e)
                return False

    def fetch_element_by_id(self, element, eid):
        '''
        Query Database for element based on id
        '''
        with self.flaskApp.app_context():
            try:
                result = element.query.filter_by(id=int(eid)).first()
                if result:
                    return result
                else:
                    return None
            except Exception as e:
                self.logger.debug(e)
                return None

    def add_organisation(self, form, upgrade = False):
        '''
        add user to database
        '''
        try:
            #with self.flaskApp.app_context():
            new_org = DBOrganisations(form.name.data)
            self.appDB.session.add(new_org)
            self.appDB.session.flush()
            self.appDB.session.commit()
            
            #Dont use self.add_location to retrieve locationid better
            new_loc = DBLocations(form.locationname.data, new_org.id,checkouts=form.checkouts.data)
            self.appDB.session.add(new_loc)
            self.appDB.session.flush()
            self.appDB.session.commit()
            self.update_scheduler(new_loc)
            form.location_id = new_loc.id
            #TODO: bring get_all_user_roles together with other stuff
            if upgrade == False:
                form.role_list = [k for k in self.get_all_user_roles().keys() if k != 1 ] 
            else:
                form.role_list = [k for k in self.get_all_user_roles().keys()]
            self.add_user(form)
            return True, f'Organisation "{form.name.data}" hinzugef&uuml;gt'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Es ist ein schwerwiegender Fehler aufgetreten (x00007).'

    def fetch_element_lists(self, element):
        #REMINDER: keep this function for debug queries
        '''
        Query Database for connections via type
        '''
        with self.flaskApp.app_context():
            try:
                eid = element.id.label("id")
                name = element.name.label("name")

                _query = self.appDB.session.query(eid, name)\
                                               .order_by(eid)
                elements = _query.all()

                if elements:
                    elist = []
                    edict = {}
                    for e in elements:
                        elist.append((str(e.id),e.name))
                        edict[str(e.id)] = e.name
                    
                    return elist, edict
                else:
                    return [],{}
            except Exception as e:
                self.logger.debug(e)
                return [],{}

    def update_organisation(self, oid, form):
        '''
        update db organisation data
        '''
        with self.flaskApp.app_context():
            try:
                organisation = self.appDB.session.query(DBOrganisations).filter_by(id=int(oid)).first()
                organisation.name = form.name.data #clean_strings(form.name.data).decode('utf-8')

                if self.appDB.session.is_modified(organisation):
                    self.appDB.session.commit()
                    return True, f'"{organisation.name}" erfolgreich geändert'
                return True, f'Für "{organisation.name}" hat sich nichts geändert.'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00005) Konnte user nicht ändern'

    def get_locations(self):
        '''
        Query Database for locations
        '''
        with self.flaskApp.app_context():
            try:
                _query = self.appDB.session.query(DBLocations)\
                                               .order_by(DBLocations.id)
                locations = _query.all()

                if locations:
                    return locations
                else:
                    return []
            except Exception as e:
                self.logger.debug(e)
                return []

    def add_location(self, name, organisation, checkouts, asco = False):
        '''
        add user to database
        '''
        try:
            with self.flaskApp.app_context():
                new_loc = DBLocations(name, organisation=int(organisation), checkouts=checkouts, asco = asco)
                self.appDB.session.add(new_loc)
                self.appDB.session.commit()
                self.update_scheduler(new_loc)
            return True, f'"{name}" erfolgreich hinzugefügt.'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Es ist ein schwerwiegender Fehler aufgetreten (x00007).'

    def update_location(self, lid, form):
        '''
        update db location data
        '''
        with self.flaskApp.app_context():
            try:
                _location = self.appDB.session.query(DBLocations).filter_by(id=int(lid)).first()
                #location.name = form.name.data
                _location.name = clean_strings(form.name.data).decode('utf-8')
                _location.checkouts = form.checkouts.data
                _location.autoscancheckout = form.autoscancheckout.data

                if self.appDB.session.is_modified(_location):
                    self.appDB.session.commit()
                    self.update_scheduler(_location)
                    return True, f'"{_location.name}" erfolgreich geändert'
                return True, f'Für "{_location.name}" hat sich nichts geändert.'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00005) Konnte user nicht ändern'

    def fetch_guests(self, date, locations = None):
        '''
        Query Database for guests based on date
        '''
        with self.flaskApp.app_context():
            try:
                guestuid = DBGuest.guid.label("guestuid")
                fname = DBGuest.fname.label("fname")
                sname = DBGuest.sname.label("sname")
                contact = DBGuest.contact.label("contact")
                checkin = DBCheckin.checkin.label("checkin")
                checkout = DBCheckin.checkout.label("checkout")
                devision = DBCheckin.devision.label("devision")

                start = date.strftime("%Y-%m-%d")
                end = (date+timedelta(days=1)).strftime("%Y-%m-%d")
                _query = self.appDB.session.query(guestuid, fname, sname, contact, checkin, checkout, devision)\
                                               .filter(and_(guestuid == DBCheckin.guid,
                                                            between(checkin, start, end),
                                                            devision.in_(locations)
                                                            ))\
                                               .order_by(devision, checkin)
                guests = _query.all()

                if guests:
                    return self.decode_guests(guests)
                else:
                    return None
            except Exception as e:
                self.logger.debug(e)
                return None

    def decode_guests(self, guests):
        '''
        decode guest data
        '''
        try:
            decoded = []
            for _g in guests:
                _guid = _g.guestuid
                _fname, _sname, _contact = self.decrypt_data(_g.fname, _g.sname, _g.contact)
                _start = _g.checkin.strftime("%d.%m.%y %H:%M:%S") if _g.checkin else ''
                _end = _g.checkout.strftime("%d.%m.%y %H:%M:%S") if _g.checkout else ''
                _devision = _g.devision 
                decoded.append(decoded_guest(_guid,
                                             _fname.decode('utf-8'),
                                             _sname.decode('utf-8'),
                                             _contact.decode('utf-8'),
                                             _start,
                                             _end,
                                             _devision
                                             )
                                )
            return decoded
        except Exception as e:
            self.logger.debug(e)
            return None

    def fetch_guest(self, guid):
        '''
        Query Database for single guest data based on guid
        '''
        with self.flaskApp.app_context():
            try:
                c_str = clean_strings(guid)#.encode('utf-8')#.encode('ascii', 'xmlcharrefreplace').strip()
                _guest = DBGuest.query.filter_by(guid=c_str).first()
                if _guest:
                    _keyfile = self.config.database['privkey']
                    fname = caesar.decrypt_string(_guest.fname, _keyfile)
                    sname = caesar.decrypt_string(_guest.sname, _keyfile)
                    contact = caesar.decrypt_string(_guest.contact, _keyfile)
                    return fname, sname, contact
                else:
                    return None, None, None

            except Exception as e:
                self.logger.debug(e)
                return None, None, None

    def count_guests(self, devision):
        '''
        retrieve guest counter from db by devision
        '''
        with self.flaskApp.app_context():
            try:
                _lookup = and_(DBCheckin.checkin+timedelta(days=1) < datetime.now(),
                              DBCheckin.checkout == None,
                              DBCheckin.devision == devision)
                _query = self.appDB.session.query(DBCheckin).filter(_lookup).order_by(DBCheckin.checkin.desc())
                _guests = _query.all()
                return len(_guests)
            except Exception as e:
                self.logger.debug(e)
                return 0

    def fetch_visits(self,guid,locations):
        '''
        Query Database for guest visits
        '''
        with self.flaskApp.app_context():
            try:
                _guestuid = DBCheckin.guid.label("guestuid")
                _checkin = DBCheckin.checkin.label("checkin")
                _checkout = DBCheckin.checkout.label("checkout")
                _devision = DBCheckin.devision.label("devision")

                _query = self.appDB.session.query(_guestuid, _checkin, _checkout, _devision)\
                                               .filter(and_(_guestuid == guid.encode('utf-8'),
                                                           DBCheckin.devision.in_(locations))
                                                      )\
                                               .order_by(_checkin)
                visits = _query.all()

                if visits:
                    return self.format_visits(visits)
                else:
                    return None
            except Exception as e:
                self.logger.debug(e)
                return None

    def format_visits(self, visits):
        '''
        decode guest data
        '''
        try:
            f_visits = []
            for _v in visits:
                _checkin = _v.checkin.strftime("%d.%m.%y %H:%M:%S") if _v.checkin else ''
                _checkout = _v.checkout.strftime("%d.%m.%y %H:%M:%S") if _v.checkout else ''
                _day = _v.checkin.strftime("%Y-%m-%d") if _v.checkin else ''
                f_visits.append(visit(_v.guestuid, _checkin, _checkout, _day, _v.devision))
                
            return f_visits
        except Exception as e:
            self.logger.debug(e)
            return None

    def encrypt_data(self, fname, sname, contact):
        '''
        encrypt guest data
        '''
        _keyfile = self.config.database['pubkey']
        fname = caesar.encrypt_string(fname, _keyfile)
        sname = caesar.encrypt_string(sname, _keyfile)
        contact = caesar.encrypt_string(contact, _keyfile)
        return fname, sname, contact

    def decrypt_data(self, fname, sname, contact):
        '''
        decrypt guest data
        '''
        _keyfile = self.config.database['privkey']
        fname = caesar.decrypt_string(fname, _keyfile)
        sname = caesar.decrypt_string(sname, _keyfile)
        contact = caesar.decrypt_string(contact, _keyfile)
        return fname, sname, contact

    @staticmethod
    def make_qr(guid, error="H", qrversion = 4, scale=1, quiet=1, preview=False):
        '''
        createw qr-code based on guid
        '''
        qr_code = pyqrcode.create(guid,error=error, version=qrversion, mode="binary")
        #qr_code.svg('file.svg', scale=scale, quiet_zone=quiet, svgclass="glad_qrcode", xmldecl=True)
        qr_code.png(".//static//codes//{}.png".format(guid), scale=scale, module_color=[0, 0, 0], background=[255, 255, 255])
        return qr_code

    def upgrade(self):
        #TODO: Keep this here only as long as needed (alpha>beta!>ceta)
        try:
            roles = self.appDB.session.query(Roles).first()
            if not roles:
                super_role = Roles(name='SuperUser')
                visit_role = Roles(name='VisitorAdmin')
                admin_role = Roles(name='UserAdmin')
                location_role = Roles(name='LocationAdmin')
                self.appDB.session.commit()
                flask.flash('Added roles', 'success')
                firstuser = self.get_current_user()
                if firstuser:
                    firstuser.roles = [super_role, visit_role, admin_role, location_role]
                    self.appDB.session.commit()
        
                    self.appDB.session.add(firstuser)
                    self.appDB.session.commit()
                    flask.flash('Updated first user', 'success')
                else:
                    raise Exception("Sorry, there is no user available. Can not perfom db upgrade")

            #check org-presence
            org = self.appDB.session.query(DBOrganisations).first()
            if not org:
                organisation = DBOrganisations(oid = 0,
                                    name='Mainorganisation')
                self.appDB.session.add(organisation)
                self.appDB.session.commit()
                flask.flash(f'First organisation "{organisation.name}" added', 'success')
                result = self.appDB.session.query(User.devision).distinct(User.devision).all()
                if result:
                    for r in list(result):
                        location = DBLocations(lid = r[0],
                                            name=f'Location_{r[0]}',
                                            organisation = 0)
                        self.appDB.session.add(location)
                        self.appDB.session.commit()
                        flask.flash(f'Location "{location.name}" added', 'success')
            result = self.appDB.session.query(ILSCMeta).first()
            version = '0.5'
            if result and result.version != version:
                result.version = version
                result.created = datetime.utcnow()
                self.appDB.session.commit()
                flask.flash(f'Updated version to {version}', 'success')
            return True, 'Upgrade successful. Now configure autoleaves, locationnames and user roles if needed.'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Upgrade failed. Hope you made a backup.'

    def init_schedulers(self):
        '''
        Query Database for locations an init cron for scheduler tas
        '''
        with self.flaskApp.app_context():
            _locs = self.get_locations()
            for l in _locs:
                if l.checkouts:
                    self.update_scheduler(l)

    def update_scheduler(self, _loc):
        '''
        update jobs
        '''
        try:
            if not _loc.checkouts == None:
                _job = self.scheduler.get_job(job_id=f"location_{_loc.id}")
                if _job:
                    self.scheduler.reschedule_job(job_id=f"location_{_loc.id}", trigger='cron', hour=_loc.checkouts, minute=0)
                else:
                    self.scheduler.add_job(self.checkout_all, 'cron', args=[_loc.id], id=f"location_{_loc.id}", hour=_loc.checkouts, minute=0)
                self.logger.info(f'Checkout(s) {_loc.checkouts} Uhr für {_loc.name} eingerichtet.')
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00010) beim task update.'

    def cleanup_everything(self):
        '''
        check and clean database
        '''
        self.clean_obsolete_checkins()
        self.clean_obsolete_contacts()

    def checkout_all(self, lid = None):
        '''
        Query Database an checkout all and fuckin check them out regardless
        '''
        with self.flaskApp.app_context():
            try:
                if not lid:
                    _guests = self.appDB.session.query(DBCheckin).filter_by(checkout=None).order_by(DBCheckin.checkin.desc()).all()
                else:
                    _guests = self.appDB.session.query(DBCheckin).filter_by(checkout=None, devision = lid).order_by(DBCheckin.checkin.desc()).all()

                for _guest in _guests:
                    _guest.checkout=datetime.now()
                self.appDB.session.commit()
                self.logger.debug(f'Checked {len(_guests)} entries out')
                return True, 'Checkout erfolgreich'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00003) beim Full-Checkout.'

    def clean_obsolete_checkins(self):
        '''
        Query Database for obsolete checkin entries and delete
        '''
        with self.flaskApp.app_context():
            try:
                days = int(self.config.app['keepdays'])
                _query = self.appDB.session.query(DBCheckin).filter(DBCheckin.checkin<datetime.now()-timedelta(days=days))
                old_checkins = _query.all()
                for checkin in old_checkins:
                    self.appDB.session.delete(checkin)
                self.appDB.session.commit()
                self.logger.debug(f'Deleted {len(old_checkins)} entries from checkins')
                return True, 'Löschen erfolgrreich erfolgreich'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00004) beim Checkin-Aufräumen.'

    def clean_obsolete_contacts(self):
        '''
        clean obsolete contact data from database
        '''
        with self.flaskApp.app_context():
            try:
                active = []
                active_checkins = self.appDB.session.query(DBCheckin).all()
                for a in active_checkins:
                    active.append(a.guid)
                old_guids = DBGuest.guid.notin_(tuple(active))
                days = int(self.config.app['keepdays'])
                _query = self.appDB.session.query(DBGuest).filter(old_guids).filter(DBGuest.created<datetime.now()-timedelta(days=days))
                remove_guests= _query.all()
                codes = []
                for r in remove_guests:
                    codes.append(r.guid)
                    self.appDB.session.delete(r)
                    self.protocol_deletion(r.guid)

                self.appDB.session.commit()
                if len(codes):
                    self.delete_qr_codes(codes)
                self.logger.debug(f'Deleted {len(remove_guests)} entries from contacts')
                return True, 'Löschen erfolgrreich erfolgreich'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00004) beim Aufräumen.'

    def delete_qr_codes(self, codes = []):
        '''
        delete not needed code files
        '''
        try:
            for c in codes:
                os.remove(f".//static//codes//{c.decode('utf-8')}.png")
        except Exception as e:
            self.logger.debug(e)

    def get_all_guids(self):
        '''
        get all checkin guids
        '''
        with self.flaskApp.app_context():
            try:
                _guests = self.appDB.session.query(DBCheckin).all()
                _guids = [] 
                for _guest in _guests:
                    _guids.append(_guest.guid)
                return _guids
            except Exception as e:
                self.logger.debug(e)

    def protocol_deletion(self, guid):
        delete = DBDeleteProtocol(guid)
        self.appDB.session.add(delete)
        #self.appDB.session.commit() 

    def decodeFlaskCookie(self, cookie):
        """Decode a Flask cookie."""
        try:
            compressed = False
            payload = cookie.replace('session=','')
    
            if payload.startswith('.'):
                compressed = True
                payload = payload[1:]
    
            data = payload.split(".")[0]
    
            data = base64_decode(data)
            if compressed:
                data = zlib.decompress(data)
    
            return data.decode("utf-8")
        except Exception as e:
            self.logger.debug(f"[Decoding error: are you sure this was a Flask session cookie? {e}]")
            return None

#
#Testfunctions
#
    def inject_random_userdata(self):
        for _ in range(0,100):
            self.test_enter_guest()

    def test_enter_guest(self):
        '''
        enter new guest into database
        '''
        try:
            guid = clean_strings(self.gen_guid()).decode('utf-8')
            fname = guid
            sname = guid
            contact = guid
            agreed = True
            fname, sname, contact = self.encrypt_data(fname, sname, contact)

            if not self.check_guid(guid):
                with self.flaskApp.app_context():
                    new_guest = DBGuest(fname = fname, sname = sname, contact = contact, guid = guid, agreed = agreed)
                    self.appDB.session.add(new_guest)
                    self.appDB.session.commit()
                self.test_guest_checkin(guid)
            else: 
                print('So ein Zufall. Die GUID existiert bereits. Versuchs bitte nochmal.')
        except Exception as e:
            self.logger.debug(e)
    
    def test_guest_checkin(self, guid):
        '''
        insert checkin into database based on guid
        '''
        try:
            guid = clean_strings(guid)
            if (not self.check_guid_is_checkedin(guid, 0)) and (not self.check_guid(guid)):
                    with self.flaskApp.app_context():
                        new_guest = DBCheckin(guid = guid)
                        self.appDB.session.add(new_guest)
                        self.appDB.session.commit()
                    return True, 'Checkin erfolgreich'
            else: return False, 'Fehler beim Checkin'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00002) beim Checkin'
