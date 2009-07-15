#
# Copyright (c) 2008 rPath, Inc.
#

from rpath_common import xmllib

from catalogService import xmlNode

class JobType(xmlNode.BaseNode):
    tag = 'jobType'
    __slots__ = [ 'id', 'type' ]
    _slotAttributes = set(['id'])

class JobTypes(xmlNode.BaseNodeCollection):
    tag = 'jobTypes'

class Handler(xmllib.DataBinder):
    jobTypeClass = JobType
    jobTypesClass = JobTypes
    def __init__(self):
        xmllib.DataBinder.__init__(self)
        for cls in [ self.jobTypeClass, self.jobTypesClass, ]:
            self.registerType(cls, cls.tag)
