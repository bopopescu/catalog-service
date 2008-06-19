#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

class BaseNode(xmllib.BaseNode):
    tag = None

    def __init__(self, attrs=None, nsMap = None, **kwargs):
        xmllib.BaseNode.__init__(self, attrs, nsMap = nsMap)
        for slot in self.__slots__:
            setattr(self, slot, None)

        for k in self.__slots__:
            method = getattr(self, "set%s%s" % (k[0].upper(), k[1:]))
            method(kwargs.get(k))

    def setName(self, name):
        pass

    def getName(self):
        return self.tag

    _getName = getName

    def getAbsoluteName(self):
        return self.tag

    def _iterChildren(self):
        for fName in self.__slots__:
            fVal = getattr(self, fName)
            if hasattr(fVal, "getElementTree"):
                yield fVal

    def _iterAttributes(self):
        return {}

    def addChild(self, node):
        nodeName = node.getName()
        if nodeName in self.__slots__:
            setattr(self, nodeName, node)

    # Magic function mapper
    def __getattr__(self, name):
        if name[:3] not in ['get', 'set']:
            raise AttributeError(name)
        slot = "%s%s" % (name[3].lower(), name[4:])
        if slot not in self.__slots__:
            raise AttributeError(name)
        if name[:3] == 'get':
            return lambda: self._get(slot)
        return lambda x: self._set(slot, x)

    def _set(self, key, value):
        setattr(self, key, None)
        if value is None:
            return self
        setattr(self, key, xmllib.GenericNode().setName(key).characters(value))
        return self

    def _get(self, key):
        val = getattr(self, key)
        if val is None:
            return None
        return val.getText()

class BaseNodeCollection(xmllib.SerializableList):
    "Base class for node collections"
