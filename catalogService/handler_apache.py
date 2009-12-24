#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import base64
import os

from conary.lib import coveragehook
from conary.lib import util
from conary import dbstore

from catalogService.utils import logger as rlogging
from restlib.http import modpython

from mint import config
from mint.db.database import Database

from catalogService import errors
from catalogService.rest.api import site
from catalogService.rest.database import RestDatabase
from catalogService.rest.middleware import auth
from catalogService.rest.middleware import response

class Request(modpython.ModPythonRequest):
    _helpDir = '/usr/share/catalog-service/help'
    _driverHelpDir = 'drivers/%(driverName)s'

class ModPythonHttpHandler(modpython.ModPythonHttpHandler):
    requestClass = Request

class ApacheRESTHandler(object):
    httpHandlerClass = ModPythonHttpHandler
    def __init__(self, pathPrefix, restdb):
        self.pathPrefix = pathPrefix
        controller = site.CatalogServiceController(restdb)
        self.handler = self.httpHandlerClass(controller)
        self.handler.addCallback(errors.ErrorMessageCallback(controller))
        self.handler.addCallback(auth.AuthenticationCallback(restdb, controller))
        # It is important that the logger callback is always called, so keep
        # this last
        self.handler.addCallback(rlogging.LoggerCallback())

    def handle(self, req):
        logger = self.getLogger(req)
        self.handler.setLogger(logger)
        rlogging.LoggerCallback.logger = logger
        return self.handler.handle(req, pathPrefix=self.pathPrefix)

    def getLogger(self, req):
        logger = rlogging.getLogger('catalog-service', None)
        logger.setAddress(req.connection.remote_ip)
        return logger

def handler(req):
    """
    The presence of this function in the module allows it to be added directly
    into apache as a mod_python handler.

    The function is for testing purposes only.
    """
    coveragehook.install()
    mintCfgPath = os.path.join(req.document_root(), '..', '..', 'mint.conf')
    mintcfg = config.getConfig(mintCfgPath)
    mintdb = Database(mintcfg)
    restdb = RestDatabase(mintcfg, mintdb)

    topLevel = os.path.join(mintcfg.basePath)

    _handler = ApacheRESTHandler(topLevel, restdb)
    return _handler.handle(req)
