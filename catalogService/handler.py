#
# Copyright (c) 2008 rPath, Inc.
#
"""
Summary
=======
This module implements the abstract interface with a web server, and HTTP
method handles for the abstraction.

URL format
==========
C{/<TOPLEVEL>/clouds}
    - (GET): enumerate available clouds
        Return an enumeration of clouds, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>
        C{<cloudName>} is generally composed of C{<cloudType>} or
        C{<cloudType>/<cloudId>}
        (for the cases where the cloud only exists as a single deployment, like
        Amazon's EC2, or, respectively, as multiple deployments, like Globus
        clouds).

C{/<TOPLEVEL>/clouds/<cloudType>}
    - (GET): enumerate available clouds for this type

C{/<TOPLEVEL>/clouds/<cloudName>/images}
    - (GET): enumerate available images for this cloud.
        - Return an enumeration of images, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>/images/<imageId>
    - (POST): publish a new image for this cloud (not valid for EC2).

C{/<TOPLEVEL>/clouds/<cloudName>/instances}
    - (GET): enumerate available images for this cloud.
        - Return an enumeration of instances, with the ID in the format::
            /<TOPLEVEL>/clouds/<cloudName>/instances/<instanceId>
    - (POST): Launch a new instance.

C{/<TOPLEVEL>/clouds/<cloudName>/instanceTypes}
    - (GET): enumerate available instance types.

C{/<TOPLEVEL>/clouds/<cloudName>/instances/<instanceId>}
    - (DELETE): Terminate a running instance.

C{/<TOPLEVEL>/clouds/<cloudName>/users/<user>/environment}
    - (GET): retrieve the launch environment

C{/<TOPLEVEL>/users/<user>}
    - (GET): Enumerate the keys defined in the store.
        - Return an enumeration of URIs in the format::
            /<TOPLEVEL>/users/<user>/<key>
    - (POST): Create a new entry in the store.

C{/<TOPLEVEL>/users/<user>/<key>}
    - (GET): Retrieve the contents of a key (if not a collection), or
      enumerate the collection.
    - (PUT): Update a key (if not a collection).
    - (POST): Create a new entry in a collection.
"""

import base64
import BaseHTTPServer

from catalogService import config
from catalogService import storage

# Monkeypatch BaseHTTPServer for older Python (e.g. the one that
# rLS1 has) to include a function that we rely on. Yes, this is gross.
if not hasattr(BaseHTTPServer, '_quote_html'):
    def _quote_html(html):
        # XXX this data is needed unre-formed by the flex frontend
        return html
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    BaseHTTPServer._quote_html = _quote_html

class StorageConfig(config.BaseConfig):
    """
    Storage configuration object.
    @ivar storagePath: Path used for persisting the values.
    @type storagePath: C{str}
    """
    def __init__(self, storagePath):
        config.BaseConfig.__init__(self)
        self.storagePath = storagePath


class BaseRESTHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    storageConfig = StorageConfig(storagePath = "storage")
    logLevel = 1
    error_message_format = '\n'.join(('<?xml version="1.0" encoding="UTF-8"?>',
            '<fault>',
            '  <code>%(code)s</code>',
            '  <message>%(message)s</message>',
            '</fault>'))
    _logDestination = None


    def do(self):
        authData = self.headers.get('Authorization', None)
        if authData and authData[:6] == 'Basic ':
            authData = authData[6:]
            authData = base64.decodestring(authData)
            authData = authData.split(':', 1)
        from catalogService.spi import  response, site
        from restlib.http import simplehttp
        baseUrl = self.path[:9]
        self.path = self.path[9:]
        self.handler = simplehttp.SimpleHttpHandler(
                                        site.SiteHandler(authData,
                                                         self.storageConfig),
                                        responseClass=response.CatalogResponse)
        self.handler.handle(self, baseUrl, authData)
    do_GET = do_POST = do_PUT = do_DELETE = do
