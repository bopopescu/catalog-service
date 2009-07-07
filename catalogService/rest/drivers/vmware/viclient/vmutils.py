#!/usr/bin/python2.4
# -*- python -*-
#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import glob, os
import httplib
import urllib
import socket
import pprint

from conary.lib import util

BUFSIZE=256 * 1024

class HTTPConnection(httplib.HTTPConnection):
    def send(self, buf):
        if self.debuglevel > 0:
            print 'send: ',
            pprint.pprint(buf)
        self.sock.sendall(buf)

class HTTPSConnection(httplib.HTTPSConnection):
    def send(self, buf):
        if self.debuglevel > 0:
            print 'send: ',
            pprint.pprint(buf)
        self.sock.sendall(buf)

def _makeConnection(url, method, headers = None, bodyStream = None):
    protocol, uri = urllib.splittype(url)
    assert(protocol in ('http', 'https'))
    host, selector = urllib.splithost(uri)
    host, port = urllib.splitport(host)

    if protocol == 'http':
        r = HTTPConnection(host, port)
    else:
        r = HTTPSConnection(host, port)

    hdrs = { 'Content-Type' : 'application/octet-stream'}
    hdrs.update(headers or {})
    if bodyStream:
        bodyStream.seek(0, 2)
        hdrs['Content-Length'] = bodyStream.tell()
        bodyStream.seek(0)

    #r.set_debuglevel(1)
    r.connect()
    r.putrequest(method, selector)
    for k, v in hdrs.items():
        r.putheader(k, str(v))
    try:
        r.endheaders()
        if bodyStream:
            # This could fail, if the device backed by this file is connected
            util.copyfileobj(bodyStream, r, bufSize=BUFSIZE,
                sizeLimit=hdrs['Content-Length'])
        return r.getresponse()
    except socket.error, e:
        raise
        response = None
        try:
            response = r.getresponse()
            r.close()
        except Exception, e:
            pass
        return response

def _putFile(inPath, outUrl, session=None):
    size = os.stat(inPath).st_size
    inFile = open(inPath)

    headers = {}
    if session:
        headers['Cookie'] =  'vmware_soap_session=%s; $Path=/' % session
    response = _makeConnection(outUrl, 'PUT', headers, inFile)

    if response and response.status not in (200, 201):
        raise RuntimeError('PUT failed: %d - %s' %(response.status,
                                                   response.reason))
    elif not response:
        raise RuntimeError('PUT failed')
    response.close()

def uploadVMFiles(v, path, vmName=None, dataCenter=None, dataStore=None):
    vmx = glob.glob(os.path.join(path, '*.vmx'))
    if not vmx:
        raise RuntimeError('no .vmx file found in %s' %path)
    if len(vmx) != 1:
        raise RuntimeError('more than one .vmx file found in %s' %path)

    filePaths = [ os.path.join(path, fn) for fn in os.listdir(path) ]

    _uploadVMFiles(v, filePaths, vmName = vmName,
        dataCenter = dataCenter, dataStore = dataStore)
    vmx = '[%s]/%s/%s' %(dataStore, vmName, os.path.basename(vmx[0]))
    return vmx

def _uploadVMFiles(v, filePaths, vmName=None, dataCenter=None, dataStore=None):
    # steal cookies from the binding's cookiejar
    session = v.getSessionUUID()
    urlBase = v.getUrlBase()
    urlPattern = '%sfolder/%s/@FILENAME@?dcPath=%s&dsName=%s' %(
        urlBase, urllib.quote(vmName), urllib.quote(dataCenter),
        urllib.quote(dataStore))

    if not dataStore:
        raise RuntimeError('dataStore currently required')
    if not dataCenter:
        raise RuntimeError('dataCenter currently required')

    for filePath in filePaths:
        fn = urllib.quote(os.path.basename(filePath))
        _putFile(filePath, urlPattern.replace('@FILENAME@', fn), session)

def _deleteVMFiles(v, filePaths, vmName=None, dataCenter=None, dataStore=None):
    # steal cookies from the binding's cookiejar
    session = v.getSessionUUID()
    urlBase = v.getUrlBase()
    urlPattern = '%sfolder/%s/@FILENAME@?dcPath=%s&dsName=%s' %(
        urlBase, urllib.quote(vmName), urllib.quote(dataCenter),
        urllib.quote(dataStore))

    if not dataStore:
        raise RuntimeError('dataStore currently required')
    if not dataCenter:
        raise RuntimeError('dataCenter currently required')

    headers = {}
    if session:
        headers['Cookie'] =  'vmware_soap_session=%s; $Path=/' % session
    for filePath in filePaths:
        filePath = os.path.basename(filePath)
        outUrl = urlPattern.replace('@FILENAME@', filePath)
        response = _makeConnection(outUrl, 'DELETE', headers)


