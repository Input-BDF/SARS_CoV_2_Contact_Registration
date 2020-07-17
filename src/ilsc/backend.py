# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''
#from sys import settrace

__all__ = ['Backend']

import logging
import os
import json
import pyqrcode
import uuid
from twisted.web.server import Site
from autobahn.twisted.resource import WebSocketResource, Resource
from sqlalchemy import and_, between
from datetime import datetime, timedelta
from .websocket import *

from ilsc.database import DBGuest, DBCheckin, User
from ilsc import caesar

from bs4 import BeautifulSoup
##
# Debug pydevd
##

#try: import pydevd;pydevd.settrace('127.0.0.1',stdoutToServer=True, stderrToServer=True) #@UnresolvedImport
#except ImportError: None # avoids throwing an Exception when not in debug mode

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

class decoded_guest():
    '''
    class for better guest returning
    '''
    def __init__(self, fname, sname, contact, checkin, checkout, devision):
        self.fname = fname
        self.sname = sname
        self.contact = contact
        self.checkin = checkin
        self.checkout = checkout
        self.devision = devision

class Backend(object):
    '''Backend class'''
    def __init__(self, config, gApp, gDatabase, superuser):
        """
        method:    __init__
        brief:    Constructs a Backend object
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.gDatabase = gDatabase
        self.gApp = gApp
        self.websocket = None
        self.superuser = superuser
        self.init_websocket()
        
    def checkout_all(self):
        '''
        Query Database an checkout all
        '''
        with self.gApp.app_context():
            try:
                _guests = DBCheckin.query.filter_by(checkout=None).order_by(DBCheckin.checkin.desc()).all()

                for _guest in _guests:
                    _guest.checkout=datetime.now()
                self.gDatabase.session.commit()
                self.logger.debug(f'Checked {len(_guests)} entries out')
                return True, 'Checkout erfolgreich'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00003) beim Full-Checkout.'

    def clean_obsolete_checkins(self):
        '''
        Query Database for obsolete checkin entries and delete
        '''
        with self.gApp.app_context():
            try:
                days = int(self.config.app['keepdays'])
                _query = DBCheckin.query.filter(DBCheckin.checkin<datetime.now()-timedelta(days=days))
                old_checkins = _query.all()
                for checkin in old_checkins:
                    self.gDatabase.session.delete(checkin)
                self.gDatabase.session.commit()
                self.logger.debug(f'Deleted {len(old_checkins)} entries from checkins')
                return True, 'Löschen erfolgrreich erfolgreich'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00004) beim Checkin-Aufräumen.'

    def clean_obsolete_contacts(self):
        '''
        clean obsolete contact data from database
        '''
        with self.gApp.app_context():
            try:
                active = []
                active_checkins = DBCheckin.query.all()
                for a in active_checkins:
                    active.append(a.guid)
                old_guids = DBGuest.guid.notin_(tuple(active))
                days = int(self.config.app['keepdays'])
                _query = DBGuest.query.filter(old_guids).filter(DBGuest.created<datetime.now()-timedelta(days=days))
                remove_guests= _query.all()
                codes = []
                for r in remove_guests:
                    codes.append(r.guid)
                    self.gDatabase.session.delete(r)
                self.gDatabase.session.commit()
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
        with self.gApp.app_context():
            try:
                _guests = DBCheckin.query.all()
                _guids = [] 
                for _guest in _guests:
                    _guids.append(_guest.guid)
                return _guids
            except Exception as e:
                self.logger.debug(e)

    def init_websocket(self):
        """
        method:    init_channels
        brief:    Initializes websocket
        """
        try:
            address = u"wss://{0}:{1}".format(self.config.websocket['address'], self.config.websocket['port'])
        except:
            address = u"wss://%s:%s" % (self.config.websocket['address'], self.config.websocket['port'])
        self.websocket = WebsocketMultiServer(address)
        self.websocket.set_backend_connections(bck_end_callback=self._ws_data_callback,
                                         bck_end_connection_made=self._ws_connection_made,
                                         bck_end_connection_lost=self._ws_connection_lost,)

    def get_websocket(self):
        """
        method:    get_websocket
        brief:    Returns websocket
        """
        # just return websocket
        return self.websocket
    
    def get_websocket_site(self):
        """
        method:    get_websocket
        brief:    Returns websocket
        """
        try:
            #root = File(".")
            root = Resource() #use Resource() else file system gets visible
            resource = WebSocketResource(self.websocket)
            # websockets resource on "/ws" path
            #root.putChild(b"ws", resource)
            root.putChild(b"", resource)
            site = Site(root)
            # just return websocket
        except Exception as e:
            print(e)
        return site
    
    def _ws_data_callback(self, data, isBinary):
        """
        method:    _ws_data_callback
        brief:    Websocket data callback
        """
        try:
            _data = json.loads(data.decode('utf-8'))
            #self.logger.debug(_data)
            if 'exists' in _data.keys():
                cleaned_guid = clean_strings(_data['exists'])
                _known = self.check_guid_today(cleaned_guid, _data['devision'])
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
        """
        method:    _ws_send_made
        brief:    Callback function sending Websocket data
        """
        self.websocket.send(json.dumps(data))
        pass
    
    def _ws_connection_made(self):
        """
        method:    _ws_connection_made
        brief:    Websocket connection made callback
        """
        self._broadcast(json.dumps({'CLIENTS' : str(len(self.websocket.clients))}))
        pass

    def _ws_connection_lost(self, reason):
        """
        method:    _ws_connection_lost
        brief:    Websocket connection lost callback
        """
        self._broadcast(json.dumps({'CLIENTS' : str(len(self.websocket.clients))}))
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
        with self.gApp.app_context():
            try:
                _entity = entity.query.filter_by(id=eid).first()
                if not _entity:
                    return False
                else:
                    self.gDatabase.session.delete(_entity)
                    self.gDatabase.session.commit()
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
        Query Database if guid exists
        '''
        with self.gApp.app_context():
            try:
                c_str = clean_strings(guid)
                _guest = DBGuest.query.filter_by(guid=c_str).all()
                if not _guest:
                    return False
                else:
                    return True
            except Exception as e:
                self.logger.debug(e)

    def check_guid_today(self, guid, devision):
        '''
        Query Database if guid exists in checkin
        '''
        with self.gApp.app_context():
            try:
                c_str = clean_strings(guid)
                lookup = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkin+timedelta(days=1) < datetime.now(),
                              DBCheckin.checkout == None,
                              DBCheckin.devision == devision)
                _query = DBCheckin.query.filter(lookup).order_by(DBCheckin.checkin.desc())
                _guest = _query.first()
                if _guest:
                    return True
                else:
                    return False
            except Exception as e:
                self.logger.debug(e)
                print(e)

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
                    with self.gApp.app_context():
                        new_guest = DBGuest(fname = fname, sname = sname, contact = contact, guid = guid, agreed = agreed)
                        self.gDatabase.session.add(new_guest)
                        self.gDatabase.session.commit()
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
            if (not self.check_guid_today(guid, devision)) and (self.check_guid(guid)):
                    with self.gApp.app_context():
                        new_guest = DBCheckin(guid = guid, devision = devision)
                        self.gDatabase.session.add(new_guest)
                        self.gDatabase.session.commit()
                    return True, 'Checkin erfolgreich'
            else: return False, 'Fehler beim Checkin'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00002) beim Checkin'

    def guest_checkout(self, guid, devision):
        '''
        Query Database if guid exists in checkin and update @ checkout time
        '''
        with self.gApp.app_context():
            try:
                c_str = clean_strings(guid)
                days = int(self.config.app['keepdays'])
                lookup = and_(DBCheckin.guid==c_str,
                              DBCheckin.checkin+timedelta(days=days)<datetime.now(),
                              DBCheckin.checkout==None,
                              DBCheckin.devision == devision)
                _query = DBCheckin.query.filter(lookup).order_by(DBCheckin.checkin.desc())
                _guest = _query.first()
                if _guest:
                    _guest.checkout=datetime.now()
                    self.gDatabase.session.commit()
                    return True, 'Checkout erfolgreich'
                else:
                    return False, 'Da gabs nix für nen checkout.'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00002) beim Checkout. Oder der wurde grad schon ausgecheckt'

    def update_user(self, uid, form):
        '''
        Query Database if guid exists in checkin and update @ checkout time
        '''
        with self.gApp.app_context():
            try:
                user = User.query.filter_by(id=int(uid)).first()
                user.username = clean_strings(form.username.data).decode('utf-8')
                user.devision = int(form.devision.data)
                #keep superuser the superuser
                user.isadmin = True if int(uid) == self.superuser else form.isadmin.data
                if self.gDatabase.session.is_modified(user):
                    self.gDatabase.session.commit()
                    return True, f'"{user.username}" erfolgreich geändert'
                return True, f'Für "{user.username}" hat sich nichts geändert.'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00005) Konnte user nicht ändern'
            
    def update_password(self, uid, form):
        '''
        Query Database if guid exists in checkin and update @ checkout time
        '''
        with self.gApp.app_context():
            try:
                user = User.query.filter_by(id=int(uid)).first()
                user.set_password(form.password.data, do_hash=True)
                if self.gDatabase.session.is_modified(user):
                    self.gDatabase.session.commit()
                    return True, f'"{user.username}" erfolgreich geändert'
                return True, f'Für "{user.username}" hat sich nichts geändert.'
            except Exception as e:
                self.logger.debug(e)
                return False, 'Schwerer Fehler (x00005) Konnte user nicht ändern'

    def fetch_user(self, uid):
        '''
        Query Database for user based on guid
        '''
        with self.gApp.app_context():
            try:
                user = User.query.filter_by(id=int(uid)).first()
                if user:
                    return user
                else:
                    return None
            except Exception as e:
                self.logger.debug(e)
                return None

    def add_user(self, username, password, devision, isadmin=False, do_hash=True):
        try:
            with self.gApp.app_context():
                new_user = User(username, password, devision, isadmin=isadmin, do_hash=do_hash)
                self.gDatabase.session.add(new_user)
                self.gDatabase.session.commit()
            return True, ''
        except Exception as e:
            self.logger.debug(e)
            return False, 'Es ist ein schwerwiegender Fehler aufgetreten (x00007).'

    def check_admin(self, uid):
        '''
        Query Database for user based on guid
        '''
        with self.gApp.app_context():
            try:
                user = User.query.filter_by(userid=str(uid)).first()
                if user:
                    return user.isadmin
                else:
                    return False
            except Exception as e:
                self.logger.debug(e)
                return False

    def get_user_devision(self, uid):
        '''
        Query Database for user based on guid
        '''
        with self.gApp.app_context():
            try:
                user = User.query.filter_by(userid=str(uid)).first()
                if user:
                    return user.devision
                else:
                    return None
            except Exception as e:
                self.logger.debug(e)
                return None

    def fetch_guests(self, date, devision = None):
        '''
        Query Database for guests based on date
        '''
        with self.gApp.app_context():
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
                _query = self.gDatabase.session.query(fname, sname, contact, checkin, checkout, devision)\
                                               .filter(and_(guestuid == DBCheckin.guid,
                                                            between(checkin, start, end)
                                                            ))\
                                               .order_by(checkin)
                _guests = _query.all()

                if _guests:
                    return self.decode_guests(_guests)
                else:
                    return None
            except Exception as e:
                self.logger.debug(e)
                return None

    def decode_guests(self, guests):
        try:
            decoded = []
            for _g in guests:
                fname, sname, contact = self.decrypt_data(_g.fname, _g.sname, _g.contact)
                start = _g.checkin.strftime("%d.%m.%y %H:%M:%S") if _g.checkin else ''
                end = _g.checkout.strftime("%d.%m.%y %H:%M:%S") if _g.checkout else ''
                devision = _g.devision 
                decoded.append(decoded_guest(fname.decode('utf-8'),
                                             sname.decode('utf-8'),
                                             contact.decode('utf-8'),
                                             start,
                                             end,
                                             devision
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
        with self.gApp.app_context():
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
        with self.gApp.app_context():
            try:
                lookup = and_(DBCheckin.checkin+timedelta(days=1) < datetime.now(),
                              DBCheckin.checkout == None,
                              DBCheckin.devision == devision)
                _query = DBCheckin.query.filter(lookup).order_by(DBCheckin.checkin.desc())
                _guests = _query.all()
                return len(_guests)
            except Exception as e:
                self.logger.debug(e)
                return 0


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

#Testfunctions
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
                with self.gApp.app_context():
                    new_guest = DBGuest(fname = fname, sname = sname, contact = contact, guid = guid, agreed = agreed)
                    self.gDatabase.session.add(new_guest)
                    self.gDatabase.session.commit()
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
            if (not self.check_guid_today(guid, 0)) and (not self.check_guid(guid)):
                    with self.gApp.app_context():
                        new_guest = DBCheckin(guid = guid)
                        self.gDatabase.session.add(new_guest)
                        self.gDatabase.session.commit()
                    return True, 'Checkin erfolgreich'
            else: return False, 'Fehler beim Checkin'
        except Exception as e:
            self.logger.debug(e)
            return False, 'Schwerer Fehler (x00002) beim Checkin'
