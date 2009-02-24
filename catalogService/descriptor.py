#!/usr/bin/python2.4
#
# Copyright (c) 2008 rPath, Inc.
#

import os
import StringIO

from rpath_common.xmllib import api1 as xmllib

from catalogService import descriptor_errors as errors
from catalogService import descriptor_nodes as dnodes

InvalidXML = xmllib.InvalidXML

class _BaseClass(xmllib.SerializableObject):
    xmlSchemaNamespace = 'http://www.w3.org/2001/XMLSchema-instance'
    schemaDir = '/usr/share/factory/schemas'

    xmlSchemaLocation = 'http://www.rpath.org/permanent/descriptor-1.0.xsd' \
                        ' descriptor-1.0.xsd'

    _rootNodeClass = None

    def __init__(self, fromStream = None, validate = False, schemaDir = None):
        xmllib.SerializableObject.__init__(self)
        self._initFields()

        if fromStream:
            if isinstance(fromStream, (str, unicode)):
                fromStream = StringIO.StringIO(fromStream)
            self.parseStream(fromStream, validate = validate,
                             schemaDir = schemaDir)

    def parseStream(self, stream, validate = False, schemaDir = None):
        """
        Initialize the current object from an XML stream.
        @param stream: An XML stream
        @type stream: C{file}
        """
        self._initFields()

        binder = self._createBinder()
        try:
            xmlObj = binder.parseFile(stream, validate = validate,
                                      schemaDir = schemaDir)
        except xmllib.SchemaValidationError, e:
            raise errors.SchemaValidationError(str(e))
        self._postprocess(xmlObj)

    def setId(self, nodeId):
        self._id = nodeId

    def getId(self):
        return self._id

    def serialize(self, stream):
        binder = xmllib.DataBinder()
        stream.write(binder.toXml(self))

    def _getLocalNamespaces(self):
        return {'xsi' : self.xmlSchemaNamespace}

    def _iterAttributes(self):
        yield ("{%s}schemaLocation" % self.xmlSchemaNamespace,
               self.xmlSchemaLocation)
        if self._id is not None:
            yield ("id", self._id)

    @classmethod
    def _createBinder(cls):
        binder = xmllib.DataBinder()
        stack = [ (cls._rootNodeClass, None) ]
        while stack:
            nodeClass, nodeClassName = stack.pop()
            if nodeClass is None:
                # A generic node. Ignore it
                continue
            binder.registerType(nodeClass, nodeClassName)
            scList = getattr(nodeClass, '_nodeDescription', [])
            for subClass, subClassName in scList:
                stack.append((subClass, subClassName))
        return binder

    @classmethod
    def _getName(cls):
        return cls._rootNodeClass.name

    def _postprocess(self, xmlObj):
        if self._rootNodeClass and not isinstance(xmlObj, self._rootNodeClass):
            raise Exception("No data found")
        nodeId = xmlObj.getAttribute('id')
        if nodeId:
            self.setId(nodeId)

class BaseDescriptor(_BaseClass):
    _rootNodeClass = dnodes.DescriptorNode

    def _postprocess(self, xmlObj):
        _BaseClass._postprocess(self, xmlObj)
        self._metadata = xmlObj.metadata
        self._dataFields.extend(xmlObj.dataFields.iterChildren())
        self._dataFieldsHash.update(dict((x.name, x)
            for x in xmlObj.dataFields.iterChildren()))

    def getMetadata(self):
        """
        @return: the metadata associated with this object
        @rtype: C{descriptor_nodes.MetadataNode}
        """
        return self._metadata

    def getDisplayName(self):
        return self._metadata.displayName

    def setDisplayName(self, displayName):
        self._metadata.displayName = displayName

    def getRootElement(self):
        return self._metadata.rootElement

    def setRootElement(self, rootElement):
        self._metadata.rootElement = rootElement

    def getDataFields(self):
        """
        @return: the data fields associated with this object
        @rtype: C{list} of C{descriptor_nodes.DataFieldNode}
        """
        return [ PresentationField(x) for x in self._dataFields ]

    def iterRawDataFields(self):
        return iter(self._dataFields)

    def addDataField(self, name, **kwargs):
        nodeType = kwargs.get('type')
        constraints = kwargs.get('constraints', [])
        descriptions = kwargs.get('descriptions', [])
        if not isinstance(descriptions, list):
            descriptions = [ descriptions ]
        help = kwargs.get('help', [])
        if not isinstance(help, list):
            help = [ help ]
        constraintsDescriptions = kwargs.get('constraintsDescriptions', [])
        default = None
        if 'default' in kwargs:
            default = kwargs['default']
        df = dnodes.DataFieldNode()
        df.name = name
        df.multiple = kwargs.get('multiple', None)
        if isinstance(nodeType, EnumeratedType):
            df.type = None
            df.enumeratedType = nodeType.toNode()
            if default is not None:
                properKeys = set(x.key for x in nodeType)
                if df.multiple:
                    if not isinstance(default, list):
                        # Silently convert a single value into a list
                        default = [ default ]
                    invalidDefaults = set(default) - properKeys
                    if invalidDefaults:
                        raise errors.InvalidDefaultValue(", ".join(sorted(invalidDefaults)))
                elif not isinstance(default, (basestring, int)):
                    # single values can only have one default value
                    raise errors.InvalidDefaultValue(default)
                elif default not in properKeys:
                    raise errors.InvalidDefaultValue(default)
        else:
            df.type = nodeType
            df.enumeratedType = None
            if default is not None:
                if df.multiple:
                    if not isinstance(default, list):
                        # Silently convert a single value into a list
                        default = [ default ]
                elif not isinstance(default, (basestring, int)):
                    # single values can only have one default value
                    raise errors.InvalidDefaultValue(default)
        df.descriptions = dnodes._Descriptions()
        df.descriptions.extend(
            [ dnodes.DescriptionNode.fromData(x) for x in descriptions ])
        df.help = [ dnodes.HelpNode.fromData(x) for x in help ]
        df.constraints = dnodes._ConstraintsNode.fromData(constraints)
        if df.constraints and constraintsDescriptions:
            df.constraints.descriptions = dnodes._Descriptions()
            # descriptions come first per XML schema. _ConstraintsNode.fromData
            # already defined the _children attribute, so we'll insert this
            # value in the front
            df.constraints._children.insert(0, df.constraints.descriptions)
            df.constraints.descriptions.extend([
                dnodes.DescriptionNode.fromData(x)
                    for x in constraintsDescriptions])
        df.default = default
        df.required = kwargs.get('required')
        df.hidden = kwargs.get('hidden')
        df.password = kwargs.get('password')
        conditional = kwargs.get('conditional')
        if conditional:
            df.conditional = dnodes._ConditionalNode.fromConditional(conditional)
        self._dataFields.extend([ df ])
        self._dataFieldsHash[df.name] = df

    def getDataField(self, name):
        if name not in self._dataFieldsHash:
            return None
        return PresentationField(self._dataFieldsHash[name])

    def getDescriptions(self):
        """
        @return: the description fields associated with this object
        @rtype: C{list} of C{description_nodes.DescriptionNode}
        """
        return self._metadata.descriptions.getDescriptions()

    def addDescription(self, description, lang=None):
        dn = dnodes.DescriptionNode.fromData(description, lang)
        if self._metadata.descriptions is None:
            self._metadata.descriptions = dnodes._Descriptions()
        self._metadata.descriptions.extend([dn])

    def _initFields(self):
        self._id = None
        self._metadata = dnodes.MetadataNode()
        self._dataFields = dnodes._DataFieldsNode()
        self._dataFieldsHash = {}

    def _iterChildren(self):
        yield self._metadata
        yield self._dataFields

class DescriptorData(_BaseClass):
    "Class for representing the descriptor data"
    __slots__ = ['_fields', '_descriptor', '_fieldsMap']

    _rootNodeClass = None

    def __init__(self, fromStream = None, validate = False, descriptor = None):
        if descriptor is None:
            raise errors.FactoryDefinitionMissing()

        self._descriptor = descriptor
        self._rootElement = descriptor.getRootElement()
        if self._rootElement is None:
            # Safe default if no default root element is supplied
            self._rootElement = dnodes.DescriptorDataNode.name
        _BaseClass.__init__(self, fromStream = fromStream)

    def _postprocess(self, xmlObj):
        _BaseClass._postprocess(self, xmlObj)
        if xmlObj.getName() != self._rootElement:
            raise errors.DataValidationError("Expected node %s, got %s"
                % (self._rootElement, xmlObj.getName()))
        for child in xmlObj.iterChildren():
            nodeName = child.getName()
            # Grab the descriptor for this field
            fieldDesc = self._descriptor.getDataField(nodeName)
            if fieldDesc is None:
                # Unsupported field
                continue
            # Disable constraint checking, we will do it at the end
            field = dnodes._DescriptorDataField(child, fieldDesc,
                checkConstraints = False)
            self._fields.append(field)
            self._fieldsMap[nodeName] = field
        self.checkConstraints()

    def _initFields(self):
        self._id = None
        self._fields = []
        self._fieldsMap = {}

    def getFields(self):
        return [ x for x in self._fields ]

    def addField(self, name, value = None):
        # Do not add the field if it was not defined
        fdesc = self._descriptor.getDataField(name)
        if fdesc is None:
            raise errors.UndefinedFactoryDataField(name)

        node = xmllib.BaseNode(name = name)
        if fdesc.multiple:
            if not isinstance(value, list):
                raise errors.DataValidationError("Expected multi-value")
            for val in value:
                val = self._cleanseValue(fdesc, val)
                val = xmllib.BaseNode(name = dnodes._ItemNode.name).characters(val)
                node.addChild(val)
        else:
            value = self._cleanseValue(fdesc, value)
            node.characters(value)

        field = dnodes._DescriptorDataField(node, fdesc)
        self._fields.append(field)
        self._fieldsMap[field.getName()] = field

    def getField(self, name):
        if name not in self._fieldsMap:
            return None
        return self._fieldsMap[name].getValue()

    def checkConstraints(self):
        errorList = []

        for field in self._fields:
            try:
                field.checkConstraints()
            except errors.ConstraintsValidationError, e:
                errorList.extend(e.args[0])

        # next, look for missing fields
        missingRequiredFields = [ x
            for x in self._descriptor.getDataFields()
            if x.name not in self._fieldsMap
                and x.required ]
        # A required field may be missing if:
        # the conditional is eq and the field is missing or the field value is
        # not what the conditional specified
        # the conditional is noteq and the field is present and its value is
        # what the conditional specified
        missingRequiredFields = [ x
            for x in missingRequiredFields
                if self._filterEqConditionals(x) ]

        for field in missingRequiredFields:
            errorList.append("Missing field: '%s'" % field.name)

        if errorList:
            raise errors.ConstraintsValidationError(errorList)

    def _filterEqConditionals(self, field):
        # Filter eq conditionals that are not satisfied
        if field.conditional is None:
            return True
        condFieldName = field.conditional.fieldName
        if condFieldName not in self._fieldsMap:
            return True
        return (self._fieldsMap[condFieldName].getValue() ==
                field.conditional.value)

    def _cleanseValue(self, fieldDescription, value):
        if not isinstance(value, basestring):
            value = str(value)
        return value


    def _iterChildren(self):
        return iter(self._fields)

    def _getLocalNamespaces(self):
        # We have no schema for descriptor data
        return {}

    def _iterAttributes(self):
        if self._id is not None:
            yield ("id", self._id)

    def _getName(self):
        return self._rootElement

class ConfigurationDescriptor(BaseDescriptor):
    "Class for representing the configuration descriptor definition"

class CredentialsDescriptor(BaseDescriptor):
    "Class for representing the credentials descriptor definition"

class LaunchDescriptor(BaseDescriptor):
    "Class for representing the launch descriptor definition"

class Description(object):
    __slots__ = [ 'description', 'lang' ]
    def __init__(self, description = None, lang = None, node = None):
        if node is None:
            self.description = description
            self.lang = lang
        else:
            self.description = node.getText()
            self.lang = node.getAttribute('lang')

class ValueWithDescription(object):
    __slots__ = [ 'key', 'descriptions' ]
    def __init__(self, key, descriptions):
        self.key = key
        if isinstance(descriptions, (str, unicode)):
            # Shortcut to simplify the setting of descriptions
            descriptions = [ (descriptions, None) ]
        self.descriptions = descriptions

    @classmethod
    def fromNode(cls, node):
        key = node.key
        descriptions = node.descriptions.getDescriptions()
        return cls(key, descriptions)

    def toNode(self):
        desc = dnodes._Descriptions()
        desc.extend(dnodes.DescriptionNode.fromData(x)
                    for x in self.descriptions)
        vwdNode = dnodes._ValueWithDescriptionNode()
        vwdNode.key = str(self.key)
        vwdNode.descriptions = desc
        return vwdNode

class EnumeratedType(list):
    @classmethod
    def fromNode(cls, node):
        inst = cls()
        for x in node.iterChildren():
            inst.append(ValueWithDescription.fromNode(x))
        return inst

    def toNode(self):
        enumer = dnodes._EnumeratedTypeNode()
        for vwd in self:
            enumer.addChild(vwd.toNode())
        return enumer

class PresentationField(object):
    __slots__ = [ 'name', 'descriptions', 'help', 'type', 'multiple', 'default',
                  'constraints', 'constraintsDescriptions', 'required',
                  'hidden', 'password', 'conditional' ]
    def __init__(self, node):
        self.name = node.name
        self.descriptions = node.descriptions.getDescriptions()
        self.help = dict((x.lang, x.href) for x in (node.help or []))
        if node.enumeratedType is None:
            self.type = node.type
        else:
            self.type = EnumeratedType.fromNode(node.enumeratedType)
        self.multiple = node.multiple
        self.default = node.default
        if not node.multiple:
            if isinstance(self.default, list):
                self.default = self.default[0]
            if self.default is not None:
                self.default = dnodes._cast(self.default, self.type)
        self.required = node.required
        self.hidden = node.hidden
        self.password = node.password
        self.constraintsDescriptions = {}
        if node.constraints:
            self.constraints = node.constraints.presentation()
            self.constraintsDescriptions = node.constraints.getDescriptions()
        else:
            self.constraints = []
        self.conditional = None
        if node.conditional:
            self.conditional = Conditional(
                fieldName = node.conditional.fieldName,
                operator = node.conditional.operator,
                value = node.conditional.value)

class Conditional(object):
    __slots__ = [ 'fieldName', 'operator', 'value' ]
    def __init__(self, fieldName = None, operator = None, value = None):
        self.fieldName = fieldName
        self.operator = operator
        self.value = value
