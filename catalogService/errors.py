#
# Copyright (c) 2008 rPath, Inc.
#
from lxml import etree

from catalogService.rest.response import XmlStringResponse
from catalogService import http_codes

class CatalogErrorResponse(XmlStringResponse):
    def __init__(self, status, message, tracebackData='', envelopeStatus=None,
                 *args, **kw):
        # See RBL-3818 - flex does not expose the content of a non-200
        # response, so we have to tunnel faults through 200.
        faultNode = etree.Element("fault")
        node = etree.Element("code")
        node.text = str(status)
        faultNode.append(node)

        node = etree.Element("message")
        node.text = message
        faultNode.append(node)

        if tracebackData:
            node = etree.Element("traceback")
            node.text = tracebackData
            faultNode.append(node)

        content = etree.tostring(faultNode, pretty_print = True,
            xml_declaration = True, encoding = 'UTF-8')
        # Prefer envelopeStatus if set, otherwise use status
        XmlStringResponse.__init__(self, content=content,
                                   status=envelopeStatus or status,
                                   message=message, *args, **kw)


class CatalogError(Exception):
    """Base class for errors from Cloud Catalog Service"""
    status = http_codes.HTTP_INTERNAL_SERVER_ERROR
    def __init__(self, message=None, status=None, *args, **kw):
        if not message:
            message = self.__class__.__doc__
        if not status:
            status = self.status
        self.status = status
        self.message = message
        self.tracebackData = kw.get('tracebackData', None)

    def __str__(self):
        return self.message

class InvalidCloudName(CatalogError):
    """Cloud name is not valid"""
    status = http_codes.HTTP_NOT_FOUND

class MissingCredentials(CatalogError):
    """Cloud credentials are not set in rBuilder"""
    status = http_codes.HTTP_BAD_REQUEST

class PermissionDenied(CatalogError):
    """Permission Denied"""
    status = http_codes.HTTP_FORBIDDEN

class ParameterError(CatalogError):
    """Errors were detected in input"""
    status = http_codes.HTTP_BAD_REQUEST
    def __init__(self, message = None):
        CatalogError.__init__(self, message = message)

class ResponseError(CatalogError):
    """Response error from remote cloud service"""
    status = http_codes.HTTP_BAD_REQUEST
    # XXX flex's httpd stack requires we pass a 200 or it will junk the content
    def __init__(self, status, message, body):
        # strip any xml tags
        if body.strip().startswith('<?xml'):
            body = ''.join(body.splitlines(True)[1:])
        CatalogError.__init__(self, message, status = status, tracebackData = body)

class CloudExists(CatalogError):
    """Target already exists"""
    status = http_codes.HTTP_CONFLICT

class HttpNotFound(CatalogError):
    """File not found"""
    status = 404

class DownloadError(CatalogError):
    """Error downloading image"""
    status = 500

class ErrorMessageCallback(object):
    def processResponse(self, request, response):
        if response.status == 200 or response.content:
            return
        return CatalogErrorResponse(status=response.status,
                            message=response.message,
                            headers=response.headers,
                            envelopeStatus = self._getEnvelopeStatus(request))

    def processException(self, request, excClass, exception, tb):
        envelopeStatus = self._getEnvelopeStatus(request)
        if isinstance(exception, CatalogError):
            return CatalogErrorResponse(status=exception.status,
                                        message=exception.message,
                                        envelopeStatus = envelopeStatus,
                                        tracebackData = exception.tracebackData)
        from restlib.http import handler
        response = handler.ExceptionCallback().processException(request,
            excClass, exception, tb)
        return CatalogErrorResponse(status = response.status,
            message = response.message,
            tracebackData = response.content,
            envelopeStatus = envelopeStatus)

    @classmethod
    def _getEnvelopeStatus(cls, request):
        if 'HTTP_X_FLASH_VERSION' not in request.headers:
            return None
        return 200
