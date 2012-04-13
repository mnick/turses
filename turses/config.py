# -*- coding: utf-8 -*-

"""
turses.config
~~~~~~~~~~~~~

This module contains a class for managing the configuration.
"""

import logging
import oauth2 as oauth
from curses import ascii
from ConfigParser import RawConfigParser
from os import environ, path, makedirs, mkdir
from gettext import gettext as _
from urlparse import parse_qsl

from . import constant
from .utils import encode
from .api.base import twitter_consumer_key, twitter_consumer_secret


class Configuration(object):
    """Class responsible for managing the configuration."""

    def __init__(self, args):
        # read defaults
        self.init_config()
        # read environment variables
        self.home = environ['HOME']
        self.get_xdg_config()
        self.get_browser()

        # generate the config file
        if args.generate_config != None:
            self.generate_config_file(args.generate_config)
            exit(0)


        self.set_path(args)
        self.check_for_default_config()
        self.conf = RawConfigParser()
        self.conf.read(self.config_file)
        if not path.isfile(self.token_file):
            self.new_account()
        else:
            self.parse_token()

        self.parse_config()

    def init_config(self):
        self.keys    = constant.key
        self.params  = constant.params
        self.palette = constant.palette

    def get_xdg_config(self):
        try:
            self.xdg_config = environ['XDG_CONFIG_HOME']
        except:
            self.xdg_config = self.home+'/.config'

    def get_browser(self):
        try:
            self.browser = environ['BROWSER']
        except:
            self.browser = ''

    def check_for_default_config(self):
        default_dir = '/turses'
        default_file = '/turses/turses.cfg'
        if not path.isfile(self.xdg_config + default_file):
            if not path.exists(self.xdg_config + default_dir):
                try:
                    makedirs(self.xdg_config + default_dir)
                except:
                    print encode(_('Couldn\'t create the directory in %s/turses')) % self.xdg_config
            self.generate_config_file(self.xdg_config + default_file)

    def generate_config_file(self, config_file):
        conf = RawConfigParser()
        conf.read(config_file)

        # COLOR
        conf.add_section('colors')
        for c in self.palette:
            conf.set('colors', c[0], c[1])
        # KEYS
        conf.add_section('keys')
        for k in self.keys:
            conf.set('keys', k, self.keys[k])
        # PARAMS
        conf.add_section('params')
        for p in self.params:
            if self.params[p] == True:
                value = 1
            elif self.params[p] == False:
                value = 0
            elif self.params[p] == None:
                continue
            else:
                value = self.params[p]

            conf.set('params', p, value)

        with open(config_file, 'wb') as config:
            conf.write(config)

        print encode(_('Generating configuration file in %s')) % config_file

    def set_path(self, args):
        # Default config path set
        if self.xdg_config != '':
            self.turses_path = self.xdg_config + '/turses/'
        else:
            self.turses_path = self.home + '/.config/turses/'
        # Setup the token file
        self.token_file = self.turses_path + 'turses.tok'
        if args.account != None:
            self.token_file += '.' + args.account
        # Setup the config file
        self.config_file = self.turses_path + 'turses.cfg'
        if args.config != None:
            self.config_file += '.' + args.config

    def new_account(self):
        self.authorization()
        self.createTokenFile()

    def parse_token(self):
        token = RawConfigParser()
        token.read(self.token_file)

        self.oauth_token = token.get('token', 'oauth_token')
        self.oauth_token_secret = token.get('token', 'oauth_token_secret')

    def parse_config(self):
        self.parse_color()
        self.parse_keys()
        self.parse_params()
        self.init_logger()

    def parse_color(self):
        for i, c in enumerate(self.palette):
            if self.conf.has_option('colors', c[0]):
                self.palette[i][1] = (self.conf.get('colors', c[0]))

    def parse_keys(self):
        for key in self.keys:
            if self.conf.has_option('keys', key):
                self.keys[key] = self.conf.get('keys', key)
            else:
                self.keys[key] = self.keys[key]

    def char_value(self, ch):
        if ch[0] == '^':
            i = 0
            while i <= 31:
                if ascii.unctrl(i) == ch.upper():
                    return i
                i +=1
        return ord(ch)

    def parse_params(self):

        # refresh (in minutes)
        if self.conf.has_option('params', 'refresh'):
            self.params['refresh']     = int(self.conf.get('params', 'refresh'))

        if self.conf.has_option('params', 'box_position'):
            self.params['refresh']     = int(self.conf.get('params', 'box_position'))

        # tweet_border
        if self.conf.has_option('params', 'tweet_border'):
            self.params['tweet_border'] = int(self.conf.get('params', 'tweet_border'))

        # Relative_time
        if self.conf.has_option('params', 'relative_time'):
            self.params['relative_time'] = int(self.conf.get('params', 'relative_time'))

        # Retweet_By
        if self.conf.has_option('params', 'retweet_by'):
            self.params['retweet_by'] = int(self.conf.get('params', 'retweet_by'))

        # Openurl_command
        #  NOTE: originally `openurl_command` configuration parameter was
        #        prioritary but I'm deprecating this, using the BROWSER
        #        environment variable instead.
        if self.browser != '':
            self.params['openurl_command'] = self.browser
        elif self.conf.has_option('params', 'openurl_command'):
            self.params['openurl_command'] = self.conf.get('params',
                'openurl_command')

        if self.conf.has_option('params', 'logging_level'):
            self.params['logging_level'] = self.conf.get('params', 'logging_level')

        if self.conf.has_option('params', 'header_template'):
            self.params['header_template'] = self.conf.get('params', 'header_template')

        if self.conf.has_option('params', 'dm_template'):
            self.params['dm_template'] = self.conf.get('params', 'dm_template')

    def init_logger(self):
        log_file = self.xdg_config + '/turses/turses.log'
        lvl = self.init_logger_level()

        logging.basicConfig(
            filename=log_file,
            level=lvl,
            format='%(asctime)s %(levelname)s - %(message)s',
            datefmt='%d/%m/%Y %H:%M:%S',
            )
        logging.info('turses starting...')

    def init_logger_level(self):
        try:
            lvl = int(self.params['logging_level'])
        except:
            # INFO is the default logging level
            return logging.INFO

        if lvl == 1:
            return logging.DEBUG
        elif lvl == 2:
            return logging.INFO
        elif lvl == 3:
            return logging.WARNING
        elif lvl == 4:
            return logging.ERROR

    # TODO: can `tweepy` be used for this?
    def authorization(self):
        ''' This function from python-twitter developers '''
        # Copyright 2007 The Python-Twitter Developers
        #
        # Licensed under the Apache License, Version 2.0 (the "License");
        # you may not use this file except in compliance with the License.
        # You may obtain a copy of the License at
        #
        #     http://www.apache.org/licenses/LICENSE-2.0
        #
        # Unless required by applicable law or agreed to in writing, software
        # distributed under the License is distributed on an "AS IS" BASIS,
        # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
        # See the License for the specific language governing permissions and
        # limitations under the License.

        base_url = 'https://api.twitter.com'

        print 'base_url:{0}'.format(base_url)


        REQUEST_TOKEN_URL = base_url + '/oauth/request_token'
        ACCESS_TOKEN_URL  = base_url + '/oauth/access_token'
        AUTHORIZATION_URL = base_url + '/oauth/authorize'
        consumer_key      = twitter_consumer_key
        consumer_secret   = twitter_consumer_secret
        oauth_consumer    = oauth.Consumer(key=consumer_key, secret=consumer_secret)
        oauth_client      = oauth.Client(oauth_consumer)

        print encode(_('Requesting temp token from Twitter'))

        resp, content = oauth_client.request(REQUEST_TOKEN_URL, 'GET')

        if resp['status'] != '200':
            print encode(_('Invalid respond, requesting temp token: %s')) % str(resp['status'])
        else:
            request_token = dict(parse_qsl(content))

            print ''
            print encode(_('Please visit the following page to retrieve needed pin code'))
            print encode(_('to obtain an Authentication Token:'))
            print ''
            print '%s?oauth_token=%s' % (AUTHORIZATION_URL, request_token['oauth_token'])
            print ''

            pincode = raw_input('Pin code? ')

            token = oauth.Token(request_token['oauth_token'], request_token['oauth_token_secret'])
            token.set_verifier(pincode)

            print ''
            print encode(_('Generating and signing request for an access token'))
            print ''

            oauth_client  = oauth.Client(oauth_consumer, token)
            resp, content = oauth_client.request(ACCESS_TOKEN_URL, method='POST', body='oauth_verifier=%s' % pincode)
            access_token  = dict(parse_qsl(content))

            if resp['status'] != '200':
                print 'response:{0}'.format(resp['status'])
                print encode(_('Request for access token failed: %s')) % resp['status']
                print access_token
                exit()
            else:
                self.oauth_token = access_token['oauth_token']
                self.oauth_token_secret = access_token['oauth_token_secret']

    def createTokenFile(self):
        if not path.isdir(self.turses_path):
            try:
                mkdir(self.turses_path)
            except:
                print encode(_('Error creating directory .config/turses'))

        conf = RawConfigParser()
        conf.add_section('token')
        conf.set('token', 'oauth_token', self.oauth_token)
        conf.set('token', 'oauth_token_secret', self.oauth_token_secret)

        with open(self.token_file, 'wb') as tokens:
            conf.write(tokens)

        print encode(_('your account has been saved'))

    def save_last_read(self, last_read):
        conf = RawConfigParser()
        conf.read(self.token_file)

        with open(self.token_file, 'wb') as tokens:
            conf.write(tokens)


CONFIG_DIR = '.turses'


class TursesConfiguration(object):
    """
    `Configuration` class creates and parses configuration files.

    There are two configuration files per account in `turses`: 

        `<username>.config`
            contains user preferences: colors, bindings, etc.

        `<username>.token`
            contains the oauth tokens

    The standar location is under $HOME directory, in a folder called `.turses`.

        ~
        |+.turses/
        | |-config
        | `-username.token
        |+...
        |-...
        `
    """
    def __init__(self, cli_args):
        """
        Create a `Configuration` object taking into account the arguments
        provided in the command line interface.
        """
        self.load_defaults()

        # generate config file and exit
        if cli_args.generate_config:
            self.generate_config_file(cli_args.generate_config)
            exit(0)

        # environment
        self.home = environ['HOME']

        # check if there is any configuration to load

    def load_defaults(self):
        """Load default values into configuration."""
        self.token   = defaults.token
        self.keys    = defaults.key
        self.params  = defaults.params
        self.filter  = defaults.filter
        self.palette = defaults.palette

    def generate_config_file(self, config_file):
        conf = RawConfigParser()
        conf.read(config_file)

        # COLOR
        conf.add_section('colors')
        for c in self.palette:
            conf.set('colors', c[0], c[1])
        # KEYS
        conf.add_section('keys')
        for k in self.keys:
            conf.set('keys', k, self.keys[k])
        # PARAMS
        conf.add_section('params')
        for p in self.params:
            if self.params[p] == True:
                value = 1
            elif self.params[p] == False:
                value = 0
            elif self.params[p] == None:
                continue
            else:
                value = self.params[p]

            conf.set('params', p, value)

        with open(config_file, 'wb') as config:
            conf.write(config)

        print encode(_('Generated configuration file in %s')) % config_file

    def get_config_files(self):
        """
        """
        # TODO
