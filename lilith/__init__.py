#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2011 posativ <info@posativ.org>. All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
# 
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
# 
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of posativ <info@posativ.org>.

VERSION = "0.1.9-dev"
VERSION_SPLIT = tuple(VERSION.split('-')[0].split('.'))

import sys
reload(sys); sys.setdefaultencoding('utf-8')

import os, logging, locale
from optparse import OptionParser, make_option, OptionGroup
from datetime import datetime

from os.path import abspath

from lilith import defaults
from lilith import filters
from lilith import views
from lilith.utils import check_conf, ColorFormatter

import yaml
from jinja2 import Template

log = logging.getLogger('lilith')
sys.path.insert(0, os.path.dirname(__package__))

class Lilith:
    """Main class for Lilith functionality.  It handles initialization,
    defines default behavior, and also pushes the request through all
    steps until the output is rendered and we're complete."""
    
    def __init__(self):
        """Sets configuration and environment and creates the Request
        object"""
        
        usage = "usage: %prog [options] init\n" + '\n' \
                + "init     - initializes base structure\n" \
                + ""
        
        options = [
            make_option("-v", "--verbose", action="store_const", dest="verbose",
                              help="debug information", const=logging.DEBUG),
            make_option("-q", "--quit", action="store_const", dest="verbose",
                              help="be silent (mostly)", const=logging.WARN,
                              default=logging.INFO),
            make_option("-f", "--force", action="store_true", dest="force",
                              help="force overwriting", default=False),
            make_option("-c", "--config", dest="conf", help="alternate conf.yaml",
                              default="conf.yaml"),
            make_option("--version", action="store_true", dest="version",
                               help="print version details", default=False),                  
            ]
            
            
        parser = OptionParser(option_list=options, usage=usage)
        ext_group = OptionGroup(parser, "conf.yaml override")
        
        for key, value in yaml.load(defaults.conf).iteritems():
            ext_group.add_option('--'+key.replace('_', '-'), action="store",
                            dest=key, metavar=value, default=value,
                            type=type(value) if type(value) != list else str)
                            
        parser.add_option_group(ext_group)
        (options, args) = parser.parse_args()
            
        console = logging.StreamHandler()
        console.setFormatter(ColorFormatter('%(message)s'))
        if options.verbose == logging.DEBUG:
            fmt = '%(msecs)d [%(levelname)s] %(name)s.py:%(lineno)s:%(funcName)s %(message)s'
            console.setFormatter(ColorFormatter(fmt))
        log = logging.getLogger('lilith')
        log.addHandler(console)
        log.setLevel(options.verbose)
        
        env = {'VERSION': VERSION, 'VERSION_SPLIT': VERSION_SPLIT}
        if options.version:
            print "lilith" + ' ' + env['VERSION']
            sys.exit(0)
        
        if len(args) < 1:
            parser.print_usage()
            sys.exit(1)
        
        # -- init -- #
        # TODO: lilith init --layout_dir=somedir to overwrite defaults
        
        if 'init' in args:
            if len(args) == 2:
                defaults.init(args[1], options.force)
            else:
                defaults.init(overwrite=options.force)
            sys.exit(0)
        
        try:
            conf = yaml.load(open(options.conf).read())
        except OSError:
            log.critical('no config file found: %s. Try "lilith init".', options.conf)
            sys.exit(1)
        
        assert check_conf(conf)
                
        conf['lilith_name'] = "lilith"
        conf['lilith_version'] = env['VERSION']

        conf['output_dir'] = conf.get('output_dir', 'output/')
        conf['entries_dir'] = conf.get('entries_dir', 'content/')
        conf['layout_dir'] = conf.get('layout_dir', 'layouts/')
        
        conf.update(options.__dict__)

        # -- run -- #
                    
        if args[0] in ['gen', 'generate', 'render']:
            self.req = {'conf': conf, 'env': env, 'data': {}}
            
            self.run()
            # from filters.md import Markdown
            # md = Markdown()
            # print md('Hallo $$beta$$-Welt', [],  *['math'])
            #self.run(request)
                
    def initialize(self, request):
        """The initialize step further initializes the Request by
        setting additional information in the ``data`` dict,
        registering plugins, and entryparsers.
        """
        
        conf = request['conf']

        # initialize the locale, will silently fail if locale is not
        # available and uses system's locale
        try:
            locale.setlocale(locale.LC_ALL, conf.get('lang', False))
        except (locale.Error, TypeError):
            # invalid locale
            log.warn('unsupported locale `%s`' % conf['lang'])
            locale.setlocale(locale.LC_ALL, '')
            conf['lang'] = locale.getlocale()

        if not conf.has_key('www_root'):
            log.warn('no `www_root` specified, using localhost:8000')
            conf['www_root'] = 'http://localhost:8000/'
        
        conf['protocol'] = conf['www_root'][0:conf['www_root'].find('://')]
        # take off the trailing slash for base_url
        if conf['www_root'].endswith("/"):
            conf['www_root'] = conf['www_root'][:-1]

        # import and initialize plugins
        filters.initialize(conf.get("ext_dir", []), request['env'],
                              exclude=conf.get("ext_ignore", []),
                              include=conf.get("ext_include", []))
        views.initialize(conf.get("ext_dir", []), request['env'])
        #conf['filters'] = [ex.__name__ for ex in filters.extensions]
        
                
    def run(self):
        """This is the main loop for lilith.  This method will run
        the handle callback to allow registered handlers to handle
        the request. If nothing handles the request, then we use the
        ``_lilith_handler``.
        """
        
        request = self.req
        conf = self.req['conf']
        #print conf['filters']
        self.initialize(request)
        
        from lilith.core import start, handle
        from lilith.filters import get_filter_chain
        from lilith.views import get_views
        
        request = start(request)
        request = handle(request)
        
        chain = get_filter_chain()
        _views = get_views()
        exec(open('conf.py')) in globals()
        
        for i, entry in enumerate(request['entrylist']):
            entry.content = entry.source
            
            _filters = entry.get('filters', entry.get('filter', views.index.filters))
            _chain = [(i, chain[j]) for i, j in [(x, chain.index(x)) for x in _filters if x in chain]]
            for i, f in _chain:
                f.__dict__['__matched__'] = i
                entry.content = f(entry.content, entry)
                
        for v in _views:
            v(request)
                
            
            #_filters.sort(key=lambda k: k.__priority__, reverse=True)
            #print _filters
        #     print chain, _filters
        #     _map = filter(lambda k: k in chain, _filters)
        #     print _map
        # for func in sorted(chain, key= lambda c: c.__priority__, reverse=True):
        #     pass
            #request = func(request)
        
#        request = format(request)
        
        
        #f = FileEntry('/Users/ich/dev/lilith/myblog/content/sample entry.txt')
        #
        #print f.source
        
        
        
        # from lilith.core import start, lilith_handler
        # 
        # # run the start callback, initialize jinja2 template
        # log.debug('cb_start')
        # request = tools.run_callback(
        #                 'start',
        #                 request,
        #                 defaultfunc=start)
        # 
        # # run the default handler
        # log.debug('cb_handle')
        # request = tools.run_callback(
        #                 "handle",
        #                 request,
        #                 defaultfunc=lilith_handler)
        #         
        # # do end callback
        # tools.run_callback('end', request)