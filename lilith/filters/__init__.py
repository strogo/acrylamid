#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2011 posativ <info@posativ.org>. All rights reserved.
# License: BSD Style, 2 clauses. see lilith.py

import sys, os, glob, fnmatch
import logging


sys.path.insert(0, os.path.dirname(__file__))
log = logging.getLogger('lilith.filters')

callbacks = []


def get_filter_chain():
    
    global callbacks
    return callbacks


def index_filters(module, env):
    """Goes through the modules' contents and indexes all the funtions/classes
    having a __call__ and __match__ attribute.
    
    Arguments:
    module -- the module to index
    """
    
    global callbacks
    
    cs = [getattr(module, c) for c in dir(module) if not c.startswith('_')]
    for mem in cs:
        if callable(mem) and hasattr(mem, '__match__'):
            callbacks.append(mem(**env))

            
def initialize(ext_dir, env, include=[], exclude=[]):
    """Imports and initializes extensions from the directories in the list
    specified by 'ext_dir'.  If no such list exists, the we don't load any
    plugins. 'include' and 'exclude' may contain a list of shell patterns
    used for fnmatch. If empty, this filter is not applied.
    
    Arguments:
    ext_dir -- list of directories
    include -- a list of filename patterns to include
    exclude -- a list of filename patterns to exclude
    """
    
    def get_name(filename):
        """Takes a filename and returns the module name from the filename."""
        return os.path.splitext(os.path.split(filename)[1])[0]
    
    def get_extension_list(ext_dir, include, exclude):
        """Load all plugins that matches include/exclude pattern in
        given lust of directories.  Arguments as in initializes(**kw)."""
        
        def pattern(name, incl, excl):
            for i in incl:
                if fnmatch.fnmatch(name, i): return True
            for e in excl:
                if fnmatch.fnmatch(name, e): return False
            if not incl:
                return True
            else:
                return False
        
        ext_list = []
        for mem in ext_dir:
            files = glob.glob(os.path.join(mem, "*.py"))
            files = [get_name(f) for f in files
                                    if pattern(get_name(f), include, exclude)]
            ext_list += files
        
        return sorted(ext_list)
    
    global plugins
    #callbacks = []
    
    exclude.extend(['mdx_*', 'rstx_*'])
    ext_dir.extend([os.path.dirname(__file__)])
    
    # handle ext_dir
    for mem in ext_dir[:]:
        if os.path.isdir(mem):
            sys.path.insert(0, mem)
        else:
            ext_dir.remove(mem)
            log.error("Extension directory '%s' does not exist. -- skipping" % mem)
            
    ext_list = get_extension_list(ext_dir, include, exclude)
    
    for mem in ext_list:
        try:
            _module = __import__(mem)
        except (ImportError, Exception), e:
            print `mem`, 'ImportError:', e
            continue
        
        index_filters(_module, env)


class InitFilterException(Exception): pass


class Filter:
    
    __priority__ = 50.0
    
    def __cmp__(self, other):
        return 0 if other in self.__match__ else 1