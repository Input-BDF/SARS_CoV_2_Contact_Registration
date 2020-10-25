# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

import flask
import flask_login
import os
import sys
import logging
import json
import ilsc

from twisted.internet import reactor, ssl
from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps

from ilsc import caesar

try:
    import urlparse
except ImportError:
    import urllib.parse

##
# Debug
##

#try: import pydevd;pydevd.settrace('127.0.0.7',stdoutToServer=True, stderrToServer=True) #@UnresolvedImport
#except ImportError: print('somethin is wrong') #None # avoids throwing an Exception when not in debug mode

##
# Global objects
##

appCommandLine = None
appConfig = None
flaskApp = None
flaskLoginManager = None
appBackend = None

##
# Globals constants
##

DEFAULT_HTTP_PORT = 8080
DEFAULT_WEBSOCKET_PORT = 8888

# magic user id of the admin
MAGIC_USER_ID = 1

##
# Config
##

appCommandLine = ilsc.CommandLine.parse_args()

appConfig = ilsc.Config()

if appCommandLine.config:
    try:
        appConfig.read(appCommandLine.config)
    except Exception as e:
        print('%s: %s' % (sys.argv[0], str(e)))
        sys.exit(1)

# Log level
if appCommandLine.log_level:
    appConfig.log['level'] = appCommandLine.log_level
# Log file
if appCommandLine.log_file:
    appConfig.log['file'] = appCommandLine.log_file

##
# Logging
##
filename=appConfig.log['file']
logging.basicConfig(format='[%(levelname)s] %(asctime)s %(module)s::%(funcName)s: %(message)s',
                    filename=appConfig.log['file'],
                    level=logging.getLevelName(appConfig.log['level']))

##
# Configuration sanity checks
# Command line options have higher priority
##
# App
if appCommandLine.static_folder:
    appConfig.app['static_folder'] = appCommandLine.static_folder
if not appConfig.app['static_folder']:
    appConfig.app['static_folder'] = 'static'
if appCommandLine.template_folder:
    appConfig.app['template_folder'] = appCommandLine.template_folder
if not appConfig.app['template_folder']:
    appConfig.app['template_folder'] = 'templates'
# Http
if appCommandLine.port:
    appConfig.http['port'] = appCommandLine.port
else:
    try:
        appConfig.http['port'] = int(appConfig.http['port'])
    except Exception as e:
        logging.warning('failed to cast http port value to int: %s' % str(e))
        logging.warning('using default http port value: %d' % (DEFAULT_HTTP_PORT))
        appConfig.http['port'] = DEFAULT_HTTP_PORT
if appCommandLine.address:
    appConfig.http['address'] = appCommandLine.address
# Websocket
if appCommandLine.websocket_port:
    appConfig.websocket['port'] = appCommandLine.websocket_port
else:
    try:
        appConfig.websocket['port'] = int(appConfig.websocket['port'])
    except Exception as e:
        logging.warning('failed to cast websocket port value to int: %s' % str(e))
        logging.warning('using default websocket port value: %d' % (DEFAULT_WEBSOCKET_PORT))
        appConfig.websocket['port'] = DEFAULT_WEBSOCKET_PORT
if appCommandLine.websocket_address:
    appConfig.websocket['address'] = appCommandLine.websocket_address
# Database path
if appCommandLine.database:
    appConfig.database['path'] = appCommandLine.database

##
# Utils
##

# Expands given path to the absolute path
def __abspath(path):
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.abspath(path)
    return path

def __render(template, **kwargs):
    try:
        try:
            hostname = urlparse.urlparse(flask.request.url).hostname
        except:
            hostname = urllib.parse.urlparse(flask.request.url).hostname
        if not appConfig.http['address']:
            appConfig.http['address'] = hostname
        if not appConfig.websocket['address']:
            appConfig.websocket['address'] = hostname
    except Exception as e:
        logging.warning(str(e))
    # pass always config data
    try: 
        user = appBackend.get_current_user()
        return flask.render_template(template,
                                     #config=appConfig.dict(),
                                     name = user.username if user else False,
                                     is_admin = user.is_admin() if user else False,
                                     roles = list(user.get_roles().keys()) if user else False,
                                     **kwargs)
    except Exception as e:
        logging.error(str(e))

def check_messages():
    '''
    check if message should be displayed
    '''
    if 'messages' in flask.session.keys():
        msg = flask.session['messages']
        flask.session.pop('messages')
        return json.loads(msg)
    return None

##
# Initialization
##

flaskApp = flask.Flask(__name__,
                   static_folder=appConfig.app['static_folder'],
                   template_folder=appConfig.app['template_folder'])
if appCommandLine.flask_config:
    appCommandLine.flask_config = __abspath(appCommandLine.flask_config)
    flaskApp.config.from_pyfile(appCommandLine.flask_config)

# database from the command line overrides one from the Flask configuration
if appConfig.database['path']:
    database_schema = 'sqlite:///'
    if appConfig.database['path'].startswith(database_schema):
        database_uri = appConfig.database['path']
    else:
        database_uri = database_schema + format(__abspath(appConfig.database['path']))
    flaskApp.config.update(SQLALCHEMY_DATABASE_URI=database_uri)
# database uri should not be empty
if 'SQLALCHEMY_DATABASE_URI' not in flaskApp.config or not flaskApp.config['SQLALCHEMY_DATABASE_URI']:
    logging.error('Invalid SQLALCHEMY_DATABASE_URI: empty')
    sys.exit(1)
# database uri should not be set to memory
if ':memory:' in flaskApp.config['SQLALCHEMY_DATABASE_URI']:
    logging.error('Invalid SQLALCHEMY_DATABASE_URI: :memory:')
    sys.exit(1)
# set random secret key if not provided in the Flask configuration
if 'SECRET_KEY' not in flaskApp.config or not flaskApp.config['SECRET_KEY']:
    flaskApp.config.update(SECRET_KEY=os.urandom(24))

# check and create private public keypair if not existing
if not caesar.check_keys_exsist(appConfig.database['privkey'], appConfig.database['pubkey']):
    caesar.generate_keys(appConfig.database['privkey'], appConfig.database['pubkey'])

# finish database initialization
ilsc.appDB.init_app(flaskApp)

# init login manager
flaskLoginManager = flask_login.LoginManager(flaskApp)

@flaskLoginManager.user_loader
def user_loader(userguid):
    user = ilsc.User.query.filter_by(userid=userguid).first()
    return user

@flaskLoginManager.unauthorized_handler
def unauthorized():
    return flask.redirect(flask.url_for('r_signin'),code=302)

def check_roles(roles=None):
    '''
    custom login_required decorator
    '''
    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            user_roles = appBackend.get_current_user().get_roles().values()
            #if user_roles and role in user_roles:
            if user_roles and any(r in roles  for r in user_roles):
                return func(*args, **kwargs)
            else:
                return __render('nope.html')
        return decorated_view
    return wrapper

@flaskApp.context_processor
def utility_processor():
    def sort_roles(roles):
        '''
        sort role objects and return list with role names used in jinja template
        '''
        resort = sorted(roles, key=lambda r: r.id, reverse=False)
        result = list(map(lambda r: r.name, resort))
        return result
    return dict(sort_roles=sort_roles)
# init backend
appBackend = ilsc.Backend(appConfig, flaskApp, ilsc.appDB, MAGIC_USER_ID)

##
# Routing
##

@flaskApp.route('/', methods=['GET', 'POST'])
def r_regform():
    form = ilsc.forms.RegisterForm()
    msg = None
    if form.validate_on_submit():
        guid = appBackend.gen_guid()
        success, msg = appBackend.enter_guest(form, guid)
        if success:
            appBackend.make_qr(guid, scale=20)
            return flask.redirect(flask.url_for('r_getqr', guid=guid, n=1),code=302)
            
    return __render('mainform.html', form = form, msg = msg)

@flaskApp.route('/qr/<guid>')
def r_getqr(guid):
    if appBackend.check_guid(guid):
        info = False
        if 'n' in flask.request.args and flask.request.args['n'] == '1':
            info = True
        return __render('qrcode.html', info=info, guid=guid,host=appConfig.http['address'], port=appConfig.http['port'])
    return flask.redirect(flask.url_for('r_regform'),code=302)
    #flask.abort(404)

@flaskApp.route('/impressum')
def r_imprint():
    return __render(appConfig.app['imprint'])

@flaskApp.route('/datenschutz')
def r_gprd():
    return __render(appConfig.app['gprd'])

@flaskApp.route('/scan', methods=['GET', 'POST'])
@flask_login.login_required
def r_scanning():
    try:
        _user = appBackend.get_current_user()
        _loc_id = _user.location.id
        _loc_name = _user.location.name

        count = appBackend.count_guests(_loc_id)
        target = {1 : flask.url_for('r_guests'),
                  2 : flask.url_for('r_guests'),
                  3 : flask.url_for('r_users'),
                  4 : flask.url_for('r_locations')
                  }
        return __render('scanning.html', wsocket=appConfig.websocket, count = count, loc_id = _loc_id, location = _loc_name, target=target)
    except Exception as e:
        print(e)

@flaskApp.route('/signin', methods=['GET', 'POST'])
def r_signin():
    if 'GET' == flask.request.method:
        return __render('signin.html')
    # POST
    errors = []
    # obtain form data
    username = flask.request.form['username'] if 'username' in flask.request.form else ''
    password = flask.request.form['password'] if 'password' in flask.request.form else ''
    # validate user
    try:
        user = ilsc.User.query.filter_by(username=username).first()
        if user and user.validate_password(password):
            if user.active:
                flask_login.login_user(user)
                return flask.redirect(flask.url_for('r_scanning'),code=302)
            else:
                errors.append(f'Fehler: Nutzer "{username}" inaktiv.')
        else:
            errors.append(f'Fehler: Passwort oder Nutzername "{username}" ist falsch.')
        logging.warning(str(errors))
        return __render('signin.html', errors=errors)
    except Exception as e:
        logging.warning(str(e))

@flaskApp.route('/signout', methods=['GET'])
@flask_login.login_required
def r_signout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for('r_signin'),code=302)

@flaskApp.route('/users')#, methods=['GET','POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser', 'UserAdmin'])
def r_users():
    '''
    render user overview
    '''
    _user = appBackend.get_current_user()
    if 'o' in flask.session.keys() and _user.is_superuser():
        _users, _lcodict = appBackend.get_organisation_users(int(flask.session['o']))
    else:
        _users, _lcodict = appBackend.get_organisation_users(_user.location.organisation)
    msg = check_messages()
    return __render('users.html', users=_users, msg=msg, loc=_lcodict)

@flaskApp.route('/user/add', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser', 'UserAdmin'])
def r_user_add():
    '''
    render user add form
    '''
    _user = appBackend.get_current_user()
    if appBackend.get_current_user().is_superuser() and 'o' in flask.session.keys():
        _, _locs_dict = appBackend.get_organisation_locations(int(flask.session['o']))
    else:
        _, _locs_dict = appBackend.get_organisation_locations(_user.location.organisation)
    _locs_dict = _locs_dict.items()

    form = ilsc.forms.UserAddForm(usr_dup_check = ilsc.User.check_duplicate)
    form.devision.choices = list(_locs_dict)
    exclude = -1 if appBackend.get_current_user().is_superuser() else 1
    form.roles.choices = ilsc.Roles.get_roles_pairs(exclude)

    if 'POST' == flask.request.method and form.validate_on_submit():
        #TODO: give feedback
        success, msg = appBackend.add_user(form)
        if success:
            flask.session['messages'] = json.dumps({"success": msg})
        else:
            flask.session['messages'] = json.dumps({"error": msg})
        return flask.redirect(flask.url_for('r_users'),code=302)
    else:
        return __render('user_edit.html',
                        form = form,
                        action = flask.url_for('r_user_add'))

@flaskApp.route('/user/edit/<uid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser', 'UserAdmin'])
def r_user_edit(uid):
    '''
    render user edit form
    '''
    _user = appBackend.get_user_by_id(uid)
    if _user and appBackend.check_organisation_permission(_user.devision) or ( appBackend.get_current_user().is_superuser() ):
        redirect = flask.redirect(flask.url_for('r_users'),code=302)
        if _user.is_superuser() and not appBackend.get_current_user().is_superuser():
            return redirect
        if _user.id == MAGIC_USER_ID and not appBackend.check_superuser():
            return redirect
        #TODO: fetch not from Backend but directly from organisation somehow
        _, _locs_dict = appBackend.get_organisation_locations(_user.location.organisation)
        _locs_dict = _locs_dict.items()
    
        form = ilsc.forms.UserForm(usr_dup_check = ilsc.User.check_duplicate, obj = _user)
        form.devision.choices = list(_locs_dict)
        exclude = -1 if appBackend.get_current_user().is_superuser() else 1
        form.roles.choices = ilsc.Roles.get_roles_pairs(exclude)

        if _user.id == MAGIC_USER_ID and not appBackend.check_superuser():
            return flask.redirect(flask.url_for('r_users'),code=302)
        if 'POST' == flask.request.method and form.validate_on_submit():
            success, msg = appBackend.update_user(_user.id, form)
            if success:
                flask.session['messages'] = json.dumps({"success": msg})
            else:
                flask.session['messages'] = json.dumps({"error": msg})
            return flask.redirect(flask.url_for('r_users'),code=302)
        form.roles.data = [int(k) for k in _user.get_roles().keys() ]

        return __render('user_edit.html',
                        form = form,
                        superuser = MAGIC_USER_ID==_user.id,
                        action = flask.url_for('r_user_edit', uid=uid),
                        goback = flask.url_for('r_users'))

    else:
        return flask.redirect(flask.url_for('r_users'),code=302)

@flaskApp.route('/_user/password/<uid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser', 'UserAdmin'])
def r_user_passwd(uid):
    '''
    render _user edit form
    '''
    _user = appBackend.get_user_by_id(uid)
    if _user and appBackend.check_organisation_permission(_user.devision) or ( appBackend.get_current_user().is_superuser() ):
        redirect = flask.redirect(flask.url_for('r_users'),code=302)
        if _user.is_superuser() and not appBackend.get_current_user().is_superuser():
            return redirect
        if _user.id == MAGIC_USER_ID and not appBackend.check_superuser():
            return redirect
        form = ilsc.forms.ChangePasswd(obj = _user)
        if 'POST' == flask.request.method and form.validate_on_submit():
            success, msg = appBackend.update_password(_user.id, form)
            if success:
                flask.session['messages'] = json.dumps({"success": msg})
            else:
                flask.session['messages'] = json.dumps({"error": msg})
            return flask.redirect(flask.url_for('r_users'),code=302)
        return __render('user_edit.html',
                        form = form,
                        superuser = MAGIC_USER_ID==_user.id,
                        action = flask.url_for('r_user_passwd',
                        uid=uid))
    else:
        return flask.redirect(flask.url_for('r_users'),code=302)

@flaskApp.route('/user/delete/<uid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser', 'UserAdmin'])
def r_user_delete(uid):
    '''
    render user delete form
    '''
    _user = appBackend.get_user_by_id(uid)
    if _user and appBackend.check_organisation_permission(_user.devision):
        redirect = flask.redirect(flask.url_for('r_users'),code=302)
        if _user.id == MAGIC_USER_ID:
            return redirect
        redirect = flask.redirect(flask.url_for('r_users'),code=302)
        if _user.is_superuser() and not appBackend.get_current_user().is_superuser():
            return redirect
        if _user.id == MAGIC_USER_ID and not appBackend.check_superuser():
            return redirect
        form = None
        return __render('user_delete.html', form = form, uid=uid)
    else:
        return flask.redirect(flask.url_for('r_users'),code=302)

@flaskApp.route('/organisations')#, methods=['GET','POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser'])
def r_organisations():
    '''
    render organisation overview page
    '''
    organisations = ilsc.DBOrganisations.query.all()
    msg = check_messages()
    return __render('organisations.html', organisations=organisations, msg=msg)

@flaskApp.route('/organisation/add', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser'])
def r_organisation_add():
    '''
    render organisation add form
    '''
    form = ilsc.forms.OrganisationRegForm(dup_check = ilsc.DBOrganisations.check_duplicate,
                                          usr_dup_check = ilsc.User.check_duplicate)
    if 'POST' == flask.request.method and form.validate_on_submit():
        #TODO: give feedback
        appBackend.add_organisation(form)
        return flask.redirect(flask.url_for('r_organisations'),code=302)
    else:
        return __render('organisations_edit.html', form=form, action=flask.url_for('r_organisation_add'))

@flaskApp.route('/organisation/edit/<oid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser'])
def r_organisation_edit(oid):
    '''
    render organisation edit form
    '''

    organisation = appBackend.fetch_element_by_id(ilsc.DBOrganisations, oid)
    if organisation:
        form = ilsc.forms.OrganisationForm(dup_check = ilsc.DBOrganisations.check_duplicate, obj=organisation)
        if 'POST' == flask.request.method and form.validate_on_submit():
            success, msg = appBackend.update_organisation(organisation.id, form)
            if success:
                flask.session['messages'] = json.dumps({"success": msg})
            else:
                flask.session['messages'] = json.dumps({"error": msg})
            return flask.redirect(flask.url_for('r_organisations'),code=302)
        
        #form = ilsc.forms.OrganisationForm(dup_check = ilsc.DBOrganisations.check_duplicate, obj = organisation)
        return __render('organisations_edit.html', form=form, action=flask.url_for('r_organisation_edit', oid=oid))

    else:
        return flask.redirect(flask.url_for('r_users'),code=302)

@flaskApp.route('/organisation/switch', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser'])
def r_organisation_switch():
    form = ilsc.forms.OrganisationSwitchForm()
    _orgs = appBackend.get_organisations().items()
    form.organisation.choices = list(_orgs)
    if 'POST' == flask.request.method and form.validate_on_submit():
        flask.session['o'] = form.organisation.data
        flask.session['messages'] = json.dumps({"success": 'Switched Organisation'})
        return flask.redirect(flask.url_for('r_users'),code=302)
    if 'o' in flask.session.keys():
        form.organisation.data = int(flask.session['o'])
    return __render('organisations_switch.html', form=form)

@flaskApp.route('/organisation/delete/<oid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['SuperUser'])
def r_organisation_delete(oid):
    '''
    location delete form
    '''
    form = None
    return __render('organisations_switch.html', form=form)

@flaskApp.route('/locations')#, methods=['GET','POST'])
@flask_login.login_required
@check_roles(roles=['LocationAdmin'])
def r_locations():
    '''
    location overview page
    '''
    _user = appBackend.get_current_user()
    if 'o' in flask.session.keys() and _user.is_superuser():
        _locs, _ = appBackend.get_organisation_locations(int(flask.session['o']))
    else:
        _locs, _ = appBackend.get_organisation_locations(_user.location.organisation)
    
    msg = check_messages()
    return __render('locations.html', locations=_locs, msg=msg)#, org = orgdict)

@flaskApp.route('/location/add', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['LocationAdmin'])
def r_location_add():
    '''
    render location add form
    '''
    form = ilsc.forms.LocationForm()
    if 'POST' == flask.request.method and form.validate_on_submit():
        #TODO: give feedback
        if appBackend.get_current_user().is_superuser() and 'o' in flask.session.keys():
            _org = int(flask.session['o'])
        else: 
            _org = appBackend.get_current_user().location.organisation
        success, msg = appBackend.add_location(name=form.name.data,
                        organisation=_org)
        if success:
            flask.session['messages'] = json.dumps({"success": msg})
        else:
            flask.session['messages'] = json.dumps({"error": msg})
        return flask.redirect(flask.url_for('r_locations'),code=302)
    else:
        return __render('locations_edit.html', form = form, action = flask.url_for('r_location_add'))

@flaskApp.route('/locations/edit/<lid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['LocationAdmin'])
def r_location_edit(lid):
    '''
    location edit form
    '''

    _location = appBackend.fetch_element_by_id(ilsc.DBLocations, lid)
    if ( _location and appBackend.check_organisation_permission(lid) ) or ( appBackend.get_current_user().is_superuser() ):
        form = ilsc.forms.LocationForm(obj = _location)
        if 'POST' == flask.request.method and form.validate_on_submit():
            success, msg = appBackend.update_location(_location.id, form)
            if success:
                flask.session['messages'] = json.dumps({"success": msg})
            else:
                flask.session['messages'] = json.dumps({"error": msg})
            return flask.redirect(flask.url_for('r_locations'),code=302)

        return __render('locations_edit.html',
                        form = form,
                        action = flask.url_for('r_location_edit', lid=lid))
    else:
        return flask.redirect(flask.url_for('r_locations'),code=302)

@flaskApp.route('/user/delete/<lid>', methods=['GET', 'POST'])
@flask_login.login_required
@check_roles(roles=['LocationAdmin'])
def r_location_delete(lid):
    '''
    location delete form
    '''
    form = None
    return __render('not_implemented.html', form = form, lid=lid)

@flaskApp.route('/guests', methods=['GET','POST'])
@flask_login.login_required
@check_roles(roles=['VisitorAdmin'])
def r_guests():
    '''
    display all guest at given day
    '''
    guests = []
    _user = appBackend.get_current_user()
    if 'o' in flask.session.keys() and _user.is_superuser():
        _, _locs_dict = appBackend.get_organisation_locations(int(flask.session['o']))
    else:
        _, _locs_dict = appBackend.get_organisation_locations(_user.location.organisation)
    form = ilsc.forms.DateLocForm()
    _locs = {-1 : 'Alle'}
    _locs.update(_locs_dict)
    form.location.choices = list(_locs.items())
    if 'POST' == flask.request.method:# and form.validate_on_submit():
        day = form.visitdate.data#.strftime('%Y-%m-%d')
        loc = int(form.location.data)
        if loc == -1 or loc == None:
            guests = appBackend.fetch_guests(day, locations = _locs_dict.keys())
        else:
            guests = appBackend.fetch_guests(day, locations = [loc,])
        return __render('guests.html', form=form, guests=guests, loc = _locs)
    form.location.data = -1
    day = form.visitdate.data
    guests = appBackend.fetch_guests(day, locations = _locs.keys())
    return __render('guests.html', form=form, guests=guests, loc = _locs)

@flaskApp.route('/visits/<guid>', methods=['GET'])
@flask_login.login_required
@check_roles(roles=['VisitorAdmin'])
def r_visits(guid):
    '''
    display all visits by guid
    '''
    visits = []
    _user = appBackend.get_current_user()
    if 'o' in flask.session.keys() and _user.is_superuser():
        _, _locs_dict = appBackend.get_organisation_locations(int(flask.session['o']))
    else:
        _, _locs_dict = appBackend.get_organisation_locations(_user.location.organisation)
    form = ilsc.forms.DateLocForm()
    _locs = {-1 : 'Alle'}
    _locs.update(_locs_dict)
    form.location.choices = list(_locs.items())
    if appBackend.check_guid(guid):
        visits = appBackend.fetch_visits(guid,_locs.keys())
    return __render('visits.html', form=form, visits=visits, loc = _locs)

@flaskApp.route('/upgrade', methods=['GET', 'POST'])
@flask_login.login_required
def r_upgrade():
    try:
        _user = appBackend.get_current_user()
        if _user.location == None:
            '''
            render organisation add form
            '''
            appBackend.upgrade()
        return flask.redirect(flask.url_for('r_locations'),code=302)
    except Exception as e:
        logging.warning('Something terribly went wrong. Hope you did an backup!')

@flaskApp.errorhandler(404)
def r_page_not_found(error):
    '''
    404 Page
    '''
    return flask.render_template('404.html', title = '404'), 404
##
# Main entry point
##
logging.debug('%r' % appConfig)
with flaskApp.app_context():
    if not ilsc.check_database(flaskApp.config['SQLALCHEMY_DATABASE_URI']):
        # initialize database
        ilsc.init_database()

def cleanup_everything():
    '''
    check and clean database
    '''
    appBackend.checkout_all()
    appBackend.clean_obsolete_checkins()
    appBackend.clean_obsolete_contacts()

#Background scheduler
scheduler = BackgroundScheduler({'apscheduler.timezone': appConfig.app['timezone']}) 
for h in appConfig.app['autocheckout']:
    scheduler.add_job(cleanup_everything, 'cron', hour=h, minute=0)
scheduler.start()

if appConfig.app['cleanonstart']:
    cleanup_everything()

#appBackend.inject_random_userdata()#just for testing
try:
    if appConfig.http['usessl']:
        priv = appConfig.http['serverpriv']
        cacert = appConfig.http['servercacert']
        certdata = ssl.DefaultOpenSSLContextFactory(priv, cacert)
        reactor.listenSSL(appConfig.http['port'], Site(WSGIResource(reactor, reactor.getThreadPool(), flaskApp)),certdata)
        reactor.listenSSL(appConfig.websocket['port'], appBackend.get_websocket_site(),certdata)
    else:
        reactor.listenTCP(appConfig.http['port'], Site(WSGIResource(reactor, reactor.getThreadPool(), flaskApp)))
        reactor.listenTCP(appConfig.websocket['port'], appBackend.get_websocket_site())
except Exception as e:
    logging.warning(str(e))
    print(e)
    
if __name__ == "__main__":
    try:
        reactor.run()
    except Exception as e:
        logging.warning(str(e))
        print(e)