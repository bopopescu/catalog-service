#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseInstance(xmlNode.BaseNode):
    tag = 'instance'
    __slots__ = [ 'id', 'instanceId', 'instanceName',
                  'instanceDescription',
                  'dnsName', 'publicDnsName', 'privateDnsName',
                  'state', 'stateCode', 'shutdownState',
                  'previousState', 'instanceType', 'launchTime',
                  'imageId', 'placement', 'kernel', 'ramdisk',
                  'reservationId', 'ownerId', 'launchIndex',
                  'cloudName', 'cloudType', 'cloudAlias',
                  'updateStatus', 
                  '_xmlNodeHash', 'launchTime', 'productCodes',
                  'placement' ]
    _slotTypeMap = dict(productCodes = list,)

class BaseInstanceUpdateStatus(xmlNode.BaseNode):
    tag = 'updateStatus'
    __slots__ = [ 'state', 'time' ]

class IntegerNode(xmlNode.xmllib.IntegerNode):
    "Basic integer node"

class BaseInstances(xmlNode.BaseNodeCollection):
    tag = "instances"

class InstanceType(xmlNode.BaseNode):
    tag = 'instanceType'
    __slots__ = [ 'id', 'instanceTypeId', 'description' ]

class InstanceTypes(xmlNode.BaseNodeCollection):
    tag = "instanceTypes"

class Handler(xmllib.DataBinder):
    instanceClass = BaseInstance
    instanceUpdateStatusClass = BaseInstanceUpdateStatus
    instancesClass = BaseInstances
    launchIndexClass = IntegerNode
    instanceTypeClass = InstanceType
    instanceTypesClass = InstanceTypes
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.launchIndexClass, 'launchIndex')
        self.registerType(self.instanceClass, self.instanceClass.tag)
        self.registerType(self.instancesClass, self.instancesClass.tag)
        self.registerType(self.instanceTypeClass, self.instanceTypeClass.tag)
        self.registerType(self.instanceTypesClass, self.instanceTypesClass.tag)
