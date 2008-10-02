#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode
from catalogService import instances

class BaseImage(xmlNode.BaseNode):
    tag = 'image'
    __slots__ = [ 'id', 'imageId', 'ownerId', 'longName', 'shortName',
            'state', 'isPublic', 'buildDescription', 'productName',
            'role', 'publisher', 'awsAccountNumber', 'buildName',
            'isPrivate_rBuilder', 'productDescription', 'is_rBuilderImage',
            'cloudName', 'cloudType', 'cloudAlias' ]
    _slotTypeMap = dict(isPublic = bool, isPrivate_rBuilder = bool,
        is_rBuilderImage = bool)

    def __init__(self, attrs = None, nsMap = None, **kwargs):

        longName = kwargs.get('longName')
        if longName:
            shortName = longName.split('/')[-1]
            kwargs['shortName'] = shortName
        else:
            # if shortName is supplied, but longName is not, delete it
            kwargs.pop('shortName', None)

        xmlNode.BaseNode.__init__(self, attrs = attrs, nsMap = nsMap, **kwargs)

    def __repr__(self):
        return "<%s:id=%s at %#x>" % (self.__class__.__name__, self.getId(),
            id(self))

class BaseImages(xmlNode.BaseNodeCollection):
    tag = "images"

class BaseImageType(xmlNode.BaseNode):
    tag = "imageType"
    __slots__ = [ 'label', 'description' ]



class BaseImageTypes(xmlNode.BaseNodeCollection):
    tag = "imageTypes"

class Handler(xmllib.DataBinder):
    imageClass = BaseImage
    imagesClass = BaseImages
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.imageClass, self.imageClass.tag)
        self.registerType(self.imagesClass, self.imagesClass.tag)

# map the way rBuilder refers to data to the call to set the node's
# data to match.
buildToNodeFieldMap = {'buildDescription': 'setBuildDescription',
            'productDescription': 'setProductDescription',
            'productName': 'setProductName',
            'isPrivate': 'setIsPrivate_rBuilder',
            'role': 'setRole',
            'createdBy': 'setPublisher',
            'awsAccountNumber': 'setAwsAccountNumber',
            'buildName': 'setBuildName'}

