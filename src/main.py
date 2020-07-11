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
from ilsc import caesar
from apscheduler.schedulers.background import BackgroundScheduler

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

gCommandLine = None
gConfig = None
gApp = None
gLoginManager = None
gBackend = None
gChart = None

##
# Globals constants
##

DEFAULT_HTTP_PORT = 8080
DEFAULT_WEBSOCKET_PORT = 8888

DEFAULT_STREAMER_HTTP_PORT = 8000
DEFAULT_BRIDGE_INTERVAL = 3600
# magic user id of the admin
MAGIC_USER_ID = 1

##
# Config
##

gCommandLine = ilsc.CommandLine.parse_args()

gConfig = ilsc.Config()

if gCommandLine.config:
    try:
        gConfig.read(gCommandLine.config)
    except Exception as e:
        print('%s: %s' % (sys.argv[0], str(e)))
        sys.exit(1)

# Log level
if gCommandLine.log_level:
    gConfig.log['level'] = gCommandLine.log_level
# Log file
if gCommandLine.log_file:
    gConfig.log['file'] = gCommandLine.log_file

##
# Logging
##
filename=gConfig.log['base'] + gConfig.log['file']
logging.basicConfig(format='[%(levelname)s] %(asctime)s %(module)s::%(funcName)s: %(message)s',
                    filename=gConfig.log['base'] + gConfig.log['file'],
                    level=logging.getLevelName(gConfig.log['level']))

##
# Configuration sanity checks
# Command line options have higher priority
##
# App
if gCommandLine.static_folder:
    gConfig.app['static_folder'] = gCommandLine.static_folder
if not gConfig.app['static_folder']:
    gConfig.app['static_folder'] = 'static'
if gCommandLine.template_folder:
    gConfig.app['template_folder'] = gCommandLine.template_folder
if not gConfig.app['template_folder']:
    gConfig.app['template_folder'] = 'templates'
# Http
if gCommandLine.port:
    gConfig.http['port'] = gCommandLine.port
else:
    try:
        gConfig.http['port'] = int(gConfig.http['port'])
    except Exception as e:
        logging.warning('failed to cast http port value to int: %s' % str(e))
        logging.warning('using default http port value: %d' % (DEFAULT_HTTP_PORT))
        gConfig.http['port'] = DEFAULT_HTTP_PORT
if gCommandLine.address:
    gConfig.http['address'] = gCommandLine.address
# Websocket
if gCommandLine.websocket_port:
    gConfig.websocket['port'] = gCommandLine.websocket_port
else:
    try:
        gConfig.websocket['port'] = int(gConfig.websocket['port'])
    except Exception as e:
        logging.warning('failed to cast websocket port value to int: %s' % str(e))
        logging.warning('using default websocket port value: %d' % (DEFAULT_WEBSOCKET_PORT))
        gConfig.websocket['port'] = DEFAULT_WEBSOCKET_PORT
if gCommandLine.websocket_address:
    gConfig.websocket['address'] = gCommandLine.websocket_address
# Database path
if gCommandLine.database:
    gConfig.database['path'] = gCommandLine.database

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
        if not gConfig.http['address']:
            gConfig.http['address'] = hostname
        if not gConfig.websocket['address']:
            gConfig.websocket['address'] = hostname
    except Exception as e:
        logging.warning(str(e))
    # pass always config data
    try: 
        return flask.render_template(template, config=gConfig.dict(), is_admin = is_admin(), **kwargs)
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

def is_admin():
    '''
    return True if user is no admin
    '''
    if '_user_id' in flask.session.keys():
        return flask.session['_user_id'] and gBackend.check_admin(flask.session['_user_id'])
    else:
        return False

def get_user_devision():
    '''
    return current user devision
    '''
    if flask.session['_user_id']:
        return gBackend.get_user_devision(flask.session['_user_id'])
    return None

##
# Initialization
##

gApp = flask.Flask(__name__,
                   static_folder=gConfig.app['static_folder'],
                   template_folder=gConfig.app['template_folder'])
if gCommandLine.flask_config:
    gCommandLine.flask_config = __abspath(gCommandLine.flask_config)
    gApp.config.from_pyfile(gCommandLine.flask_config)

# database from the command line overrides one from the Flask configuration
if gConfig.database['path']:
    database_schema = 'sqlite:///'
    if gConfig.database['path'].startswith(database_schema):
        database_uri = gConfig.database['path']
    else:
        database_uri = database_schema + format(__abspath(gConfig.database['path']))
    gApp.config.update(SQLALCHEMY_DATABASE_URI=database_uri)
# database uri should not be empty
if 'SQLALCHEMY_DATABASE_URI' not in gApp.config or not gApp.config['SQLALCHEMY_DATABASE_URI']:
    logging.error('Invalid SQLALCHEMY_DATABASE_URI: empty')
    sys.exit(1)
# database uri should not be set to memory
if ':memory:' in gApp.config['SQLALCHEMY_DATABASE_URI']:
    logging.error('Invalid SQLALCHEMY_DATABASE_URI: :memory:')
    sys.exit(1)
# set random secret key if not provided in the Flask configuration
if 'SECRET_KEY' not in gApp.config or not gApp.config['SECRET_KEY']:
    gApp.config.update(SECRET_KEY=os.urandom(24))

# check and create private public keypair if not existing
if not caesar.check_keys_exsist(gConfig.database['privkey'], gConfig.database['pubkey']):
    caesar.generate_keys(gConfig.database['privkey'], gConfig.database['pubkey'])

# finish database initialization
ilsc.gDatabase.init_app(gApp)

# init login manager
gLoginManager = flask_login.LoginManager(gApp)

@gLoginManager.user_loader
def user_loader(userid):
    return ilsc.User.query.filter_by(userid=userid).first()

@gLoginManager.unauthorized_handler
def unauthorized():
    return flask.redirect(flask.url_for('r_signin'),code=302)

# init backend
gBackend = ilsc.Backend(gConfig, gApp, ilsc.gDatabase, MAGIC_USER_ID)

##
# Routing
##

@gApp.route('/', methods=['GET', 'POST'])
def r_regform():
    form = ilsc.forms.RegisterForm()
    msg = None
    if form.validate_on_submit():
        guid = gBackend.gen_guid()
        success, msg = gBackend.enter_guest(form, guid)
        if success:
            gBackend.make_qr(guid, scale=20)
            return flask.redirect(flask.url_for('r_getqr', guid=guid, n=1),code=302)
            
    return __render('mainform.html', form = form, msg = msg)

@gApp.route('/qr/<guid>')
def r_getqr(guid):
    if gBackend.check_guid(guid):
        info = False
        if 'n' in flask.request.args and flask.request.args['n'] == '1':
            info = True
        return __render('qrcode.html', info=info, guid=guid,host=gConfig.http['address'], port=gConfig.http['port'])
    return flask.redirect(flask.url_for('r_regform'),code=302)
    #flask.abort(404)

@gApp.route('/impressum')
def r_imprint():
    return __render(gConfig.app['imprint'])

@gApp.route('/datenschutz')
def r_gprd():
    return __render(gConfig.app['gprd'])

@gApp.route('/scan', methods=['GET', 'POST'])
@flask_login.login_required
def r_scanning():
    try:
        devision_id = get_user_devision()
        devision = gConfig.app['devisions'][devision_id]
        count = gBackend.count_guests(devision_id)
        return __render('scanning.html', wsocket=gConfig.websocket, count = count, devision_id = devision_id, devision = devision)
    except Exception as e:
        print(e)

@gApp.route('/signin', methods=['GET', 'POST'])
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

@gApp.route('/signout', methods=['GET'])
@flask_login.login_required
def r_signout():
    flask_login.logout_user()
    return flask.redirect(flask.url_for('r_signin'),code=302)

@gApp.route('/users')#, methods=['GET','POST'])
@flask_login.login_required
def r_users():
    if not is_admin():
        return __render('nope.html')

    devisions = gConfig.app['devisions']
    users = ilsc.User.query.all()
    msg = check_messages()
    return __render('users.html', users=users, msg=msg, dev = devisions)

@gApp.route('/guests', methods=['GET','POST'])
@flask_login.login_required
def r_guests():
    if not is_admin():
        return __render('nope.html')
    guests = []
    devisions = gConfig.app['devisions']
    form = ilsc.forms.DateForm()
    if form.validate_on_submit():
        date = form.visitdate.data#.strftime('%Y-%m-%d')
        guests = gBackend.fetch_guests(date)
    return __render('guests.html', form=form, guests=guests, devisions = devisions)

@gApp.route('/user/edit/<uid>', methods=['GET', 'POST'])
@flask_login.login_required
def r_user_edit(uid):
    '''
    render user edit form
    '''
    if not is_admin():
        return __render('nope.html')

    devisions = []
    for i in range(len(gConfig.app['devisions'])):
        devisions.append((str(i),gConfig.app['devisions'][i]))
    form = ilsc.forms.UserForm(choices = devisions)
    user = gBackend.fetch_user(uid)

    if user:
        if 'POST' == flask.request.method and form.validate_on_submit():
            success, msg = gBackend.update_user(user.id, form)
            if success:
                flask.session['messages'] = json.dumps({"success": msg})
            else:
                flask.session['messages'] = json.dumps({"error": msg})
            return flask.redirect(flask.url_for('r_users'),code=302)
        
        form = ilsc.forms.UserForm(obj = user, choices = devisions)
        return __render('user_edit.html', form = form, uid=uid, superuser = MAGIC_USER_ID==user.id)

    else:
        return flask.redirect(flask.url_for('r_users'),code=302)

@gApp.route('/user/password/<uid>', methods=['GET', 'POST'])
@flask_login.login_required
def r_user_passwd(uid):
    '''
    render user edit form
    '''
    if not is_admin():
        return __render('nope.html')

    form = ilsc.forms.ChangePasswd()
    user = gBackend.fetch_user(uid)
    if user:
        if 'POST' == flask.request.method and form.validate_on_submit():
            success, msg = gBackend.update_password(user.id, form)
            if success:
                flask.session['messages'] = json.dumps({"success": msg})
            else:
                flask.session['messages'] = json.dumps({"error": msg})
            return flask.redirect(flask.url_for('r_users'),code=302)
        
        form = ilsc.forms.ChangePasswd(obj = user)
        return __render('user_password.html', form = form, uid=uid, superuser = MAGIC_USER_ID==user.id)
    else:
        return flask.redirect(flask.url_for('r_users'),code=302)

@gApp.route('/user/delete/<uid>', methods=['GET', 'POST'])
@flask_login.login_required
def r_user_delete(uid):
    '''
    render user delete form
    '''
    if not is_admin():
        return __render('nope.html')

    form = None
    return __render('user_delete.html', form = form, uid=uid)

@gApp.route('/user/add', methods=['GET', 'POST'])
@flask_login.login_required
def r_user_add():
    '''
    render user delete form
    '''
    if not is_admin():
        return __render('nope.html')

    devisions = []
    for i in range(len(gConfig.app['devisions'])):
        devisions.append((str(i),gConfig.app['devisions'][i]))
    form = ilsc.forms.UserAddForm(choices = devisions)
    devisions = []
    if 'POST' == flask.request.method and form.validate_on_submit():
        #TODO: give feedback
        gBackend.add_user(username=form.username.data,
                        password=form.password.data,
                        devision = form.devision.data,
                        isadmin = form.isadmin.data,
                        do_hash=True)
        return flask.redirect(flask.url_for('r_users'),code=302)
    else:
        return __render('user_add.html', form = form, choices = devisions)
    return __render('user_add.html', form = form, choices = devisions)

@gApp.route('/user-remove', methods=['POST'])
@flask_login.login_required
def r_user_remove():
    if not is_admin():
        return __render('nope.html')

    try:
        _userid = flask.request.form['user-id'] if 'user-id' in flask.request.form else 0
        if MAGIC_USER_ID == int(_userid): raise ValueError('user with id=%s cannot be removed' % str(_userid))
        user = ilsc.User.query.filter_by(id=int(_userid)).first() if _userid else None
        if user:
            ilsc.gDatabase.session.delete(user)
            ilsc.gDatabase.session.commit()
            return flask.jsonify({})
    except Exception as e:
        logging.warning(str(e))
    return ('', 204)

@gApp.errorhandler(404)
def r_page_not_found(error):
    return flask.render_template('404.html', title = '404'), 404
##
# Main entry point
##
logging.debug('%r' % gConfig)
with gApp.app_context():
    if not ilsc.check_database(gApp.config['SQLALCHEMY_DATABASE_URI']):
        # initialize database
        ilsc.init_database()

def cleanup_everything():
    '''
    check and clean database
    '''
    gBackend.checkout_all()
    gBackend.clean_obsolete_checkins()
    gBackend.clean_obsolete_contacts()

#Background scheduler
scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/Berlin'})
job = scheduler.add_job(cleanup_everything, 'cron', hour=gConfig.app['autocheckout'], minute=0)
scheduler.start()

# initialize scheduler with your preferred timezone
cleanup_everything()


#gBackend.inject_random_userdata()#just for testing
try:
    if gConfig.http['usessl']:
        priv = gConfig.http['serverpriv']
        cacert = gConfig.http['servercacert']
        certdata = ssl.DefaultOpenSSLContextFactory(priv, cacert)
        reactor.listenSSL(gConfig.http['port'], Site(WSGIResource(reactor, reactor.getThreadPool(), gApp)),certdata)
        reactor.listenSSL(gConfig.websocket['port'], gBackend.get_websocket_site(),certdata)
    else:
        reactor.listenTCP(gConfig.http['port'], Site(WSGIResource(reactor, reactor.getThreadPool(), gApp)))
        reactor.listenTCP(gConfig.websocket['port'], gBackend.get_websocket_site())
except Exception as e:
    logging.warning(str(e))
    print(e)
    
if __name__ == "__main__":
    try:
        reactor.run()
    except Exception as e:
        logging.warning(str(e))
        print(e)