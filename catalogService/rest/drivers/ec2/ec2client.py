import os
import urllib
from boto.ec2.connection import EC2Connection
from boto.exception import EC2ResponseError

from catalogService.instances import BaseInstances
from catalogService.images import BaseImages
from catalogService import images

CATALOG_DEF_SECURITY_GROUP = 'catalog-default'
CATALOG_DEF_SECURITY_GROUP_DESC = 'Default EC2 Catalog Security Group'
CATALOG_DEF_SECURITY_GROUP_PERMS = (
        # proto  start_port  end_port
        ('tcp',  22,         22),
        ('tcp',  80,         80),
        ('tcp',  443,        443),
        ('tcp',  8003 ,      8003),
)

class LaunchInstanceParameters(object):
    def __init__(self, xmlString=None):
        if xmlString:
            self.load(xmlString)

    def load(self, xmlString):
        from catalogService import newInstance
        node = newInstance.Handler().parseString(xmlString)
        image = node.getImage()
        imageId = image.getId()
        self.imageId = self._extractId(imageId)
        self.minCount = node.getMinCount() or 1
        self.maxCount = node.getMaxCount() or 1
        keyPair = node.getKeyPair()
        if not keyPair:
            raise errors.ParameterError('keyPair was not specified')
        keyName = keyPair.getId()
        self.keyName = self._extractId(keyName)

        self.securityGroups = []
        clientSuppliedRemoteIP = None
        for sg in (node.getSecurityGroups() or []):
            sgId = sg.getId()
            sgId = self._extractId(sgId)
            self.securityGroups.append(sgId)
            if sgId == CATALOG_DEF_SECURITY_GROUP:
                clientSuppliedRemoteIP = sg.getRemoteIp()

        self.remoteIPAddress = clientSuppliedRemoteIP

        self.userData = node.getUserData()

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'm1.small'
        else:
            instanceType = instanceType.getId() or 'm1.small'
            instanceType = self._extractId(instanceType)
        self.instanceType = instanceType

    @staticmethod
    def _extractId(value):
        if value is None:
            return None
        return urllib.unquote(os.path.basename(value))


class EC2Client(object):
    cloudType = 'ec2'

    def __init__(self, mintClient, cfg, instanceFactory, imageFactory):
        self._cfg = cfg
        self._mintClient = mintClient
        self._client = None
        self._instanceFactory = instanceFactory
        self._imageFactory = imageFactory

    def _getClient(self):
        if not self._client:
            self._mintAuth = self._mintClient.checkAuth()
            if not self._mintAuth.authorized:
                raise PermissionDenied
            cred = self._mintClient.getEC2CredentialsForUser(
                                                 self._mintAuth.userId)
            self._client = EC2Connection(cred['awsPublicAccessKeyId'],
                                         cred['awsSecretAccessKey'])
        return self._client

    client = property(_getClient)

    def listClouds(self):
        return ['ec2']

    def updateCloud(self, cloudId, parameters):
        parameters = CloudParameters(parameters)
        pass

    def listInstanceIds(self, cloudId):
        rs = self.client.get_all_instances(instance_ids = None)
        return [ x.id for x in rs]

    def listImageIds(self, cloudId):
        rs = self.client.get_all_images(image_ids = None)
        return [ x.id for x in rs]

    def launchInstanceParameters(self):
        return LaunchInstanceParameters()

    def launchInstances(self, cloudId, imageIds, parameters):
        for imageId in imageIds:
            self.launchInstance(cloudId, imageId, parameters)

    def launchInstance(self, cloudId, xmlString, requestIPAddress):
        parameters = LaunchInstanceParameters(xmlString)
        if (parameters.remoteIPAddress
            and CATALOG_DEF_SECURITY_GROUP in parameters.securityGroups):
            # Create/update the default security group that opens TCP
            # ports 80, 443, and 8003 for traffic from the requesting IP address
            self._updateCatalogDefaultSecurityGroup(parameters.remoteIPAddress)

        reservation = self.client.run_instances(parameters.imageId,
                min_count=parameters.minCount,
                max_count=parameters.maxCount,
                key_name=parameters.keyName,
                security_groups=parameters.securityGroups,
                user_data=parameters.userData,
                instance_type=parameters.instanceType)
        return self._getInstancesFromReservation(reservation)

    def terminateInstances(self, cloudId, instanceIds):
        resultSet = self.client.terminate_instances(instance_ids=instanceIds)
        return self._getInstancesFromResult(resultSet)

    def terminateInstance(self, cloudId, instanceId):
        return self.terminateInstances(cloudId, [instanceId])[0]

    def getAllInstances(self, cloudId):
        return self.getInstances(cloudId, None)

    def getInstances(self, cloudId, instanceIds):
        resultSet = self.client.get_all_instances(instance_ids = instanceIds)
        instances = BaseInstances()
        for reservation in resultSet:
            instances.extend(self._getInstancesFromReservation(reservation))
        return instances

    def getAllImages(self, cloudId):
        return self.getImages(cloudId, None)

    def getImages(self, cloudId, imageIds):
        rs = self.client.get_all_images(image_ids = imageIds)
        # avoid returning amazon kernel images.
        rs = [ x for x in rs if x.id.startswith('ami-') ]
        return self._getImagesFromResult(rs)

    def _updateCatalogDefaultSecurityGroup(self, remoteIPAddress):
        assert(remoteIPAddress)
        # add the security group if it's not present already
        try:
            self.client.create_security_group(CATALOG_DEF_SECURITY_GROUP,
                    CATALOG_DEF_SECURITY_GROUP_DESC)
        except EC2ResponseError, e:
            if e.status == 400 and e.code == 'InvalidGroup.Duplicate':
                pass # ignore this error
            else:
                raise errors.ResponseError(e.status, e.reason, e.body)

        # open ingress for ports 80, 443, and 8003 on TCP
        # for the IP address
        for proto, from_port, to_port in CATALOG_DEF_SECURITY_GROUP_PERMS:
            try:
                self.client.authorize_security_group(CATALOG_DEF_SECURITY_GROUP,
                        ip_protocol=proto, from_port=from_port, to_port=to_port,
                        cidr_ip='%s/32' % remoteIPAddress)
            except EC2ResponseError, e:
                if e.status == 400 and e.code == 'InvalidPermission.Duplicate':
                    pass # ignore this error
                else:
                    raise errors.ResponseError(e.status, e.reason, e.body)

        return CATALOG_DEF_SECURITY_GROUP

    def _getInstancesFromResult(self, resultSet):
        instanceList = BaseInstances()
        for i in resultSet:
            instanceList.append(self._getInstance(i))
        return instanceList

    def _getInstancesFromReservation(self, reservation):
        instances = BaseInstances()
        for instance in reservation.instances:
            instances.append(self._getInstance(instance, reservation))
        return instances

    def _getInstance(self, instance, reservation=None):
        properties = {'placement' : instance.placement,
                      'kernel'    : instance.kernel,
                      'ramdisk'   : instance.ramdisk}
        if reservation:
            properties.update(ownerId=reservation.owner_id,
                              resevationId=reservation.id)
        if hasattr(instance, 'ami_launch_index'):
            properties.update(launchIndex=instance.ami_launch_index)
        i = self._instanceFactory(id=instance.id, instanceId=instance.id,
                                  launchTime=instance.launch_time,
                                  imageId=instance.image_id,
                                  cloudName='ec2',
                                  cloudType='ec2',
                                  cloudAlias='ec2',
                                  **properties)
        return i


    def _getImagesFromResult(self, results):
        imageList = BaseImages()
        for image in results:
            i = self._imageFactory(id=image.id, imageId=image.id,
                                   ownerId=image.ownerId,
                                   longName=image.location,
                                   state=image.state,
                                   isPublic=image.is_public,
                                   cloudName='ec2', cloudType='ec2',
                                   cloudAlias='ec2')
            imageList.append(i)
        imageDataDict = self._mintClient.getAllAMIBuilds()
        for image in imageList:
            imageData = imageDataDict.get(image.imageId.getText(), {})
            image.setIs_rBuilderImage(bool(imageData))
            for key, methodName in images.buildToNodeFieldMap.iteritems():
                getattr(image, methodName)(imageData[key])
        return imageList
