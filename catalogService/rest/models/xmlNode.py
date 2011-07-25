#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import inspect

import urllib

import rpath_xmllib as xmllib
from conary.lib import digestlib

class BaseNode(xmllib.BaseNode):
    tag = None
    # Hint for a slot's type
    _slotTypeMap = {}
    # Hint for attribute vs. sub-element
    _slotAttributes = set()

    # Overrides for whatever was provided in the constructor
    # This is useful, for instance, for providing some quasi-immutable
    # defaults
    _constructorOverrides = {}


    def __init__(self, attrs=None, nsMap = None, **kwargs):
        xmllib.BaseNode.__init__(self, attrs, nsMap = nsMap)
        for slot in self.__slots__:
            setattr(self, slot, None)

        kwargs.update(self._constructorOverrides)
        for k in set(self.__slots__):
            if k.startswith('_'):
                # Private variable, do not set
                continue
            val = kwargs.get(k)
            # If the slot is an attribute, look it up in the attribute list
            # too
            if k in self._slotAttributes and attrs is not None:
                val = attrs.get(k, val)
            self._set(k, val)

    def setName(self, name):
        pass

    def getName(self):
        return self.tag

    _getName = getName

    def getAbsoluteName(self):
        return self.tag

    def _iterChildren(self):
        sublementsFound = False
        for fName in sorted(set(self.__slots__)):
            if fName.startswith('_'):
                continue
            if fName in self._slotAttributes:
                continue
            fVal = getattr(self, fName)
            if hasattr(fVal, "getElementTree"):
                subelementsFound = True
                yield fVal
            if isinstance(fVal, MultiItemList):
                for fv in fVal:
                    yield fv
        # We don't allow for mixed content
        if not sublementsFound:
            text = self.getText()
            if text:
                yield text

    def _iterAttributes(self):
        ret = {}
        for fName in self._slotAttributes:
            fVal = getattr(self, fName)
            if fVal is not None:
                ret[fName] = str(fVal)
        return ret.iteritems()

    def addChild(self, node):
        nodeName = node.getName()
        if nodeName in self.__slots__:
            if self._setMultiItem(nodeName, node):
                return
            else:
                setattr(self, nodeName, node)

    def getElementTree(self, *args, **kwargs):
        eltree = xmllib.BaseNode.getElementTree(self, *args, **kwargs)
        if '_xmlNodeHash' not in self.__slots__ or self._xmlNodeHash is not None:
            return eltree
        # Compute the checksum
        csum = digestlib.sha1()
        csum.update(xmllib.etree.tostring(eltree, pretty_print = False,
                    xml_declaration = False, encoding = 'UTF-8'))
        self._xmlNodeHash = csum.hexdigest()
        eltree.attrib['xmlNodeHash'] = self._xmlNodeHash
        return eltree

    # Magic function mapper
    def __getattr__(self, name):
        if name[:3] not in ['get', 'set']:
            raise AttributeError(name)
        if name[3] == '_':
            # We don't allow for slots starting with _ to be magically handled
            raise AttributeError(name)
        slot = "%s%s" % (name[3].lower(), name[4:])
        if slot not in self.__slots__:
            slot = name[3:]
            if slot not in self.__slots__:
                raise AttributeError(name)
        if name[:3] == 'get':
            return lambda: self._get(slot)
        return lambda x: self._set(slot, x)

    def _set(self, key, value):
        setattr(self, key, None)
        if value is None:
            return self
        slotType = self._slotTypeMap.get(key)
        if key in self._slotAttributes:
            if slotType == bool:
                if not isinstance(value, basestring):
                    value = xmllib.BooleanNode.toString(value)
            # Attributes are strings
            setattr(self, key, str(value))
            return self
        if hasattr(value, 'getElementTree') and value._getName() == key:
            # This catches the case where we have a list defined as one of the
            # sub-nodes for this object
            setattr(self, key, value)
            return self
        if slotType == bool or isinstance(slotType, xmllib.BooleanNode):
            cls = xmllib.BooleanNode
            value = cls.toString(value)
        elif slotType == int or isinstance(value, int):
            cls = xmllib.IntegerNode
            value = str(value)
        elif slotType == list:
            coll = BaseNodeCollection()
            coll.tag = key
            coll.extend(xmllib.GenericNode().setName("item").characters(x)
                for x in value)
            setattr(self, key, coll)
            return self
        elif self._setMultiItem(key, value):
            return self
        else:
            cls = xmllib.GenericNode
        setattr(self, key, cls().setName(key).characters(value))
        return self

    def _setMultiItem(self, key, value):
        slotType = self._slotTypeMap.get(key)
        if not (inspect.isclass(slotType) and
                        issubclass(slotType, BaseNode) and
                        getattr(slotType, 'multiple', None)):
            return False
        currentVal = getattr(self, key, None)
        if currentVal is None:
            currentVal = MultiItemList()
            setattr(self, key, currentVal)
        if value is None:
            return True
        if not isinstance(value, list):
            value = [ value ]
        for v in value:
            if isinstance(v, slotType):
                currentVal.append(v)
            else:
                currentVal.append(slotType(None, self.getNamespaceMap(), v))
        return True

    def _get(self, key):
        val = getattr(self, key)
        if val is None:
            return None
        slotType = self._slotTypeMap.get(key)
        if slotType == bool:
            if hasattr(val, 'getText'):
                val = val.getText()
            return xmllib.BooleanNode.fromString(val)
        if slotType == list:
            return [ x.getText() for x in val.iterChildren()]
        if slotType == int:
            if hasattr(val, 'getText'):
                val = val.getText()
            return int(val)
        if isinstance(val, xmllib.IntegerNode):
            return val.finalize()
        if isinstance(val, BaseNode) and val.__slots__:
            return val
        if hasattr(val, 'iterChildren'):
            children = [ x for x in val.iterChildren()
                if not isinstance(x, basestring) ]
            if children:
                # Mixed mode not supported: we don't extract the text out of
                # nodes with children
                return val
        if hasattr(val, 'getText'):
            return val.getText()
        # Well, this may be a list of values. Just return it
        return val

    @classmethod
    def urlquote(cls, data):
        return urllib.quote(data, safe = "")

    def __repr__(self):
         return "<%s:id=%s at %#x>" % (self.__class__.__name__, self.getId(),
            id(self))

class BaseNodeCollection(xmllib.SerializableList):
    "Base class for node collections"

    def __init__(self, attrs = None, nsMap = None):
        xmllib.SerializableList.__init__(self)
        self._attrs = attrs or {}
        self._nsMap = nsMap or {}

    def setName(self, name):
        "No-op, it should be defined by the class"

    def getNamespaceMap(self):
        return self._nsMap.copy()

    def finalize(self):
        return self

    def characters(self, data):
        return self

    addChild = xmllib.SerializableList.append
    getName = xmllib.SerializableList._getName

class MultiItemList(list):
    """
    List containing items that get serialized without a wrapping parent node
    """

class BaseMultiNode(BaseNode):
    tag = "softwareVersion"
    multiple = True

    def __init__(self, attrs = None, nsMap = None, item = None):
        BaseNode.__init__(self, attrs, nsMap = nsMap)
        if item is None:
            return
        self.characters(str(item))

    def getId(self):
        return "%s: %s" % (self.tag, self.getText())



class Handler(xmllib.DataBinder):
    "Base xml handler"

    def registerType(self, typeClass, *args, **kwargs):
        xmllib.DataBinder.registerType(self, typeClass, *args, **kwargs)
        if not hasattr(typeClass, '_slotTypeMap'):
            return
        registered = set()
        toRegister = [typeClass]
        while toRegister:
            tClass = toRegister.pop()
            for name, valType in tClass._slotTypeMap.items():
                if valType in registered:
                    continue
                if issubclass(valType, BaseNode):
                    xmllib.DataBinder.registerType(self, valType, valType.tag)
                    toRegister.append(valType)
                    registered.add(valType)
