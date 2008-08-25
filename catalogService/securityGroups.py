#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

import xmlNode

class BaseSecurityGroup(xmlNode.BaseNode):
    tag = 'securityGroup'
    __slots__ = [ 'id', 'ownerId', 'groupName', 'description',
            'remoteIp' ]

class BaseSecurityGroups(xmlNode.BaseNodeCollection):
    tag = 'securityGroups'

class Handler(xmllib.DataBinder):
    securityGroupClass = BaseSecurityGroup
    securityGroupsClass = BaseSecurityGroups
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        self.registerType(self.securityGroupClass, self.securityGroupClass.tag)
        self.registerType(self.securityGroupsClass, self.securityGroupsClass.tag)
