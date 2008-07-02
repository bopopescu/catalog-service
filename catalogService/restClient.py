#
# Copyright (c) 2008 rPath, Inc.
#

import base64
import httplib
import urllib

class ResponseError(Exception):
    def __init__(self, status, reason, headers, response):
        Exception.__init__(self)
        self.status = status
        self.reason = reason
        self.headers = headers
        self.response = response

class Client(object):
    def __init__(self, url):
        self.scheme = None
        self.user = None
        self.passwd = None
        self.host = None
        self.port = None
        self.path = None

        urltype, url = urllib.splittype(url)
        if urltype:
            self.scheme = urltype.lower()

        host, self.path = urllib.splithost(url)
        if host:
            user_passwd, host = urllib.splituser(host)
            self.host, self.port = urllib.splitport(host)
            if self.port is not None:
                self.port = int(self.port)
            if user_passwd:
                self.user, self.passwd = urllib.splitpasswd(user_passwd)

        if self.scheme not in ['http', 'https']:
            raise ValueError(self.scheme)

        self._connection = None

    def setUserPassword(self, username, password):
        self.user = username
        self.passwd = password

    def connect(self):
        if self.scheme == 'http':
            cls = httplib.HTTPConnection
        else:
            cls = httplib.HTTPAConnection
        self._connection = cls(self.host, port = self.port)
        self._connection.connect()
        return self

    def request(self, method, body=None, headers=None):
        if headers is None:
            headers = {}
        if self.user is not None and self.passwd is not None:
            user_pass = base64.b64encode('%s:%s' % (self.user, self.passwd))
            headers['Authorization'] = 'Basic %s' % user_pass
        self._connection.request(method, self.path, body = body,
                                 headers = headers)
        resp = self._connection.getresponse()
        if resp.status != 200:
            raise ResponseError(resp.status, resp.reason, resp.msg, resp)
        return resp

