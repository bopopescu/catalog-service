#!/usr/bin/python
#
# Copyright (c) 2008-2009 rPath, Inc.  All Rights Reserved.
#

import os
import urllib

from catalogService.rest.models import clouds
from catalogService.rest.models import cloud_types

class NodeFactory(object):
    __slots__ = [ 'cloudConfigurationDescriptorFactory',
        'credentialsDescriptorFactory',
        'cloudFactory', 'cloudTypeFactory', 'credentialsFactory',
        'credentialsFieldFactory', 'credentialsFieldsFactory',
        'imageFactory', 'instanceFactory', 'instanceUpdateStatusFactory',
        'instanceTypeFactory', 'instanceLaunchJobFactory',
        'jobTypeFactory', 'keyPairFactory',
        'securityGroupFactory',
        'baseUrl', 'cloudType', 'cloudName', 'userId']

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            if not slot.startswith('_'):
                setattr(self, slot, kwargs.get(slot, None))

    def newCloudType(self, *args, **kwargs):
        node = self.cloudTypeFactory(*args, **kwargs)
        cloudTypeId = self._getCloudTypeUrl(self.cloudType)
        node.setId(cloudTypeId)
        node.setCloudInstances(cloud_types.CloudInstances(
            href = self.join(cloudTypeId, 'instances')))
        node.setDescriptorCredentials(cloud_types.DescriptorCredentials(
            href = self.join(cloudTypeId, 'descriptor', 'credentials')))
        node.setDescriptorInstanceConfiguration(
            cloud_types.DescriptorInstanceConfiguration(
                href = self.join(cloudTypeId, 'descriptor', 'configuration')))
        return node

    def newCloud(self, *args, **kwargs):
        node = self.cloudFactory(*args, **kwargs)
        cloudId = self.getCloudUrl(node)
        node.setId(cloudId)
        cloudType = clouds.Type(href = self._getCloudTypeUrl(self.cloudType)).characters(self.cloudType)
        node.setType(cloudType)
        node.setImages(clouds.Images(href = self.join(cloudId, 'images')))
        node.setInstances(clouds.Instances(href = self.join(cloudId, 'instances')))
        node.setUserCredentials(clouds.UserCredentials(href = self.join(cloudId, 'users', self.userId, 'credentials')))
        node.setConfiguration(clouds.Configuration(href = self.join(cloudId,
            'configuration')))
        node.setDescriptorLaunch(clouds.DescriptorLaunch(href =
                                 self.join(cloudId, 'descriptor', 'launch')))
        searchParams = dict(cloudName = node.getCloudName(),
                cloudType = self.cloudType,
                status = 'Running')
        node.setActiveJobs(clouds.ActiveJobs(href = self.getJobSearchUrl(
            'instance-launch', searchParams)))
        return node

    def newCloudConfigurationDescriptor(self, descr):
        cloudTypeUrl = self._getCloudTypeUrl(self.cloudType)

        for field in descr.iterRawDataFields():
            for helpNode in (field.help or []):
                href = helpNode.href
                if '://' not in href:
                    helpNode.href = "%s/help/%s" % (cloudTypeUrl, href)
        return descr

    def newCredentialsDescriptor(self, *args, **kwargs):
        node = self.credentialsDescriptorFactory(*args, **kwargs)
        return node

    def newCloudConfigurationDescriptorData(self, node):
        node.setId(self.join(self._getCloudUrlFromParams(), 'configuration'))
        return node

    def newCredentialsDescriptorData(self, node):
        node.setId(self.join(self._getCloudUrlFromParams(), 'users', self.userId,
            'credentials'))
        return node

    def newCredentials(self, valid, fields = None):
        # XXX deprecated
        if fields is None:
            fields = []
        fieldsNode = self.credentialsFieldsFactory()
        for credName, credVal in fields:
            fieldsNode.append(self.credentialsFieldFactory(
                credentialName = credName, value = credVal))
        credsNode = self.credentialsFactory(fields = fieldsNode,
                                            valid = valid)
        return credsNode

    def newImage(self, *args, **kwargs):
        node = self.imageFactory(*args, **kwargs)
        node.setId(self.getImageUrl(node))
        node.setCloudType(self.cloudType)
        return node

    def newInstance(self, *args, **kwargs):
        node = self.instanceFactory(*args, **kwargs)
        node.setId(self.getInstanceUrl(node))
        node.setCloudType(self.cloudType)
        updateStatus = self.instanceUpdateStatusFactory()
        updateStatus.setState('')
        updateStatus.setTime('')
        node.setUpdateStatus(updateStatus)
        return node

    def newInstanceLaunchJob(self, *args, **kwargs):
        node = self.instanceLaunchJobFactory(*args, **kwargs)
        node.setId(self.getJobIdUrl(node.getId(), node.getType()))
        node.setImageId(self._getImageUrl(node, node.getImageId()))
        for result in (node.getResult() or []):
            href = result.getHref()
            if href:
                result.setHref(self._getInstanceUrl(node, href))
        return node

    def newLaunchDescriptor(self, descriptor):
        cloudTypeUrl = self._getCloudTypeUrl(self.cloudType)

        for field in descriptor.iterRawDataFields():
            for helpNode in field.help:
                href = helpNode.href
                if '://' not in href:
                    helpNode.href = "%s/help/%s" % (cloudTypeUrl, href)
        return descriptor

    def newSecurityGroup(self, instanceId, secGroup):
        sgId = self.join(self._getCloudUrl(self.cloudType, self.cloudName),
            'instances', instanceId, 'securityGroups',
            self._quote(secGroup.getId()))
        secGroup.setId(sgId)
        return secGroup

    def getJobIdUrl(self, jobId, jobType):
        jobId = os.path.basename(jobId)
        jobType = os.path.basename(jobType)
        return self.join(self.baseUrl, 'jobs', 'types', jobType, 'jobs',
            jobId)

    def getJobSearchUrl(self, jobType, params):
        q = urllib.quote_plus
        params = sorted(params.items())
        params = '&'.join("%s=%s" % (q(x, safe=':'), q(y, safe=':'))
            for (x, y) in params)
        return self.join(self.baseUrl, 'jobs', 'types', jobType,
            'jobs?' + params)

    @classmethod
    def join(cls, *args):
        """Join the arguments into a URL"""
        if args[0][-1] == '/':
            args = list(args)
            args[0] = args[0][:-1]
        return '/'.join(args)

    def getCloudUrl(self, node):
        return self._getCloudUrl(self.cloudType, node.getCloudName())

    def getImageUrl(self, node):
        return self._getImageUrl(node, node.getId())

    def _getImageUrl(self, node, imageId):
        if imageId is None:
            return None
        return self.join(self.getCloudUrl(node), 'images',
                        self._quote(imageId))

    def getInstanceUrl(self, node):
        return self._getInstanceUrl(node, node.getId())

    def _getInstanceUrl(self, node, instanceId):
        if instanceId is None:
            return None
        return self.join(self.getCloudUrl(node), 'instances',
                        self._quote(instanceId))

    def _getCloudTypeUrl(self, cloudType):
        return self.join(self.baseUrl, 'clouds', cloudType)

    def _getCloudUrl(self, cloudType, cloudName):
        return self.join(self._getCloudTypeUrl(cloudType), 'instances',
            cloudName)

    def _getCloudUrlFromParams(self):
        return self._getCloudUrl(self.cloudType,
                                 self.cloudName)

    @classmethod
    def _quote(cls, data):
        return urllib.quote(data, safe="")
