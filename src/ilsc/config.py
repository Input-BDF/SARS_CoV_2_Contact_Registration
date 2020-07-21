# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

__all__ = ['CommandLine', 'Config']

import argparse
import configparser
import logging

CommandLine = argparse.ArgumentParser()
CommandLine.add_argument('-p', '--port', type=int, action='store', help='Specify local port for remote HTTP connects')
CommandLine.add_argument('-a', '--address', type=str, action='store', help='Specify address for remote HTTP connects')
CommandLine.add_argument('--websocket-port', type=int, action='store', help='Specify local port for remote WebSocket connects')
CommandLine.add_argument('--websocket-address', type=str, action='store', help='Specify address for remote WebSocket connects')
CommandLine.add_argument('-c', '--config', type=str, action='store', help='Specify path to the configuration file')
CommandLine.add_argument('--flask-config', type=str, action='store', help='Specify path to the flask configuration')
CommandLine.add_argument('--static-folder', type=str, action='store', help='Specify path to the flask static folder')
CommandLine.add_argument('--template-folder', type=str, action='store', help='Specify path to the flask template folder')
CommandLine.add_argument('-d', '--database', type=str, action='store', help='Specify database uri')
CommandLine.add_argument('--channels', type=str, action='store', nargs='*', help='Specify path(s) to channels.conf file(s)')
CommandLine.add_argument('--log-level', type=str, action='store', choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'], help='Set log level')
CommandLine.add_argument('--log-file', type=str, action='store', help='Set log file')

"""
class: Config
brief: Reads configuration file
"""
class Config(object):
    # Private attributes
    MULTIPLE_VALUE_DELIMITER = ','
    # Public methods
    def __init__(self):
        # Logger
        self.logger = logging.getLogger(__name__)
        # Public attributes
        self.app = {}
        self.app['static_folder'] = ''
        self.app['template_folder'] = ''
        self.app['contactmail'] = ''
        self.app['keepdays'] = 2
        self.app['autocheckout'] = 6
        self.app['devisions'] = ('Biergarten','bc','café','bd','bh','bi')
        self.app['imprint'] = 'default_imprint.html'
        self.app['gprd'] = 'default_gprd.html'
        self.app['cleanonstart'] = False
        self.app['timezone'] = 'Europe/Berlin'
        # Section [http]
        self.http = {}
        self.http['address'] = ''
        self.http['port'] = '8080'
        self.http['usessl'] = False
        self.http['servercacert'] = ''
        self.http['serverpriv'] = ''
        # Section [websocket]
        self.websocket = {}
        self.websocket['address'] = ''
        self.websocket['port'] = '8888'
        # Section [database]
        self.database = {}
        self.database['path'] = ''
        self.database['pubkey'] = ''
        self.database['privkey'] = ''
        # Section [log]
        self.log = {}
        self.log['base'] = '/tmp'
        self.log['file'] = ''
        self.log['level'] = 'INFO'

        # All sections
        self.sections = [
            'app',
            'http',
            'websocket',
            'database',
            'log'
        ]
        # Parsed files
        self.files = []
    """
    method:    read
    brief:    Reads a configuration file
    """
    def read(self, filename):
        try:
            self.parser = configparser.ConfigParser(allow_no_value=True)
            self.files = self.parser.read(filename, 'utf-8')
            if not self.files:
                raise IOError('failed to read a configuration file')
            for section in self.parser.sections():
                for key, value in self.parser.items(section):
                    try:
                        getattr(self, section)[key] = value
                    except AttributeError as e:
                        self.logger.warning(str(e))
                        pass
            if self.app['devisions'] and isinstance(self.app['devisions'], str):
                self.app['devisions'] = tuple(self.app['devisions'].split(','))
            if self.app['autocheckout'] and isinstance(self.app['autocheckout'], str):
                self.app['autocheckout'] = tuple(self.app['autocheckout'].split(','))
            if self.app['cleanonstart'] and isinstance(self.app['cleanonstart'], str):
                self.app['cleanonstart'] = self.app['cleanonstart'] in ('True', 'true', '1', 1)
            self.http['usessl'] = True if self.http['usessl'] in ('True','true','1') else False 

        except (configparser.ParsingError, configparser.MissingSectionHeaderError) as e:
            self.logger.warning(str(e))
            raise IOError('failed to parse a configuration file')
    
    def write(self, section, data):
        if not self.files:
            raise IOError('failed to read a configuration file')
        if not self.parser:
            raise IOError('config parser not present')
        try:
            for key, value in data.items():
                self.parser.set(section, key, value)
            self.logger.debug('----------------')
            self.logger.debug(self.files)
            # Writing our configuration file to 'filename'
            with open(self.files[0], 'wb') as configfile:
                self.parser.write(configfile)
            return True
        except:
            return False
        
    """
    method:    __repr__
    brief:    Returns a string representation of a Config object
    """
    def __repr__(self):
        s = 'from <%s>\n' % ('; '.join(self.files))
        for section in self.sections:
            s += '[%s]\n' % (section)
            try:
                for key, value in getattr(self, section).items():
                    s += '\t%s = %s\n' % (str(key), str(value))
            except AttributeError as a:
                print(a)
                pass
        return s
    """
    method:    __repr__
    brief:    Returns a string representation of a Config object
    """
    def dict(self):
        d = {}
        for section in self.sections:
            d[section] = {}
            try:
                for key, value in getattr(self, section).items():
                    d[section][key] = value
            except AttributeError as a:
                print(a)
                pass
        return d
    
##
# Test Entry Point
##

import sys

def main():
    if 2 > len(sys.argv):
        sys.exit('Usage: %s <main.cfg>' % sys.argv[0])
    logging.basicConfig(format='[%(levelname)s] %(asctime)s %(module)s::%(funcName)s: %(message)s', level=logging.DEBUG)
    config = Config()
    # read input file
    config.read(sys.argv[1])
    logging.debug(config)

if __name__ == "__main__":
    main()
