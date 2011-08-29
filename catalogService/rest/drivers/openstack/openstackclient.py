#
# Copyright (c) 2011 rPath, Inc.  All Rights Reserved.
#

import os

from catalogService import errors
from catalogService.rest import baseDriver
from catalogService.rest.models import images
from catalogService.rest.models import instances

try:
    from novaclient.v1_1.client import Client as NovaClient
#    from glance.client import Client
except ImportError:
    NovaClient = None #pyflakes=ignore

class OpenStack_Image(images.BaseImage):
    "OpenStack Image"

# This is provided by the nova api
#class OpenStack_InstanceTypes(instances.InstanceTypes):
#    "OpenStack Instance Types"
#
#    idMap = [
#        ('xenent.small', "Small"),
#        ('xenent.medium', "Medium"),
#    ]

# Nova address
# Nova port
# Glance address (until apis are integrated)
# Glance port
_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>OpenStack Configuration</displayName>
    <descriptions>
      <desc>Configure OpenStack</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Nova Server</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/novaServerName.html'/>
    </field>
    <field>
      <name>nova_port</name>
      <descriptions>
        <desc>Nova Port</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/novaPortNumber.html'/>
    </field>
    <field>
      <name>glance_server</name>
      <descriptions>
        <desc>Glance Server</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/glanceServerName.html'/>
    </field>
    <field>
      <name>glance_port</name>
      <descriptions>
        <desc>Glance Port</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/glancePortNumber.html'/>
    </field>
    <field>
      <name>alias</name>
      <descriptions>
        <desc>Name</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/alias.html'/>
    </field>
    <field>
      <name>description</name>
      <descriptions>
        <desc>Full Description</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/description.html'/>
    </field>
  </dataFields>
</descriptor>"""

# User Name
# Auth Token
_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>OpenStack User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for OpenStack</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>username</name>
      <descriptions>
        <desc>User Name</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 32 characters</desc>
        </descriptions>
        <length>255</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>auth_token</name>
      <descriptions>
        <desc>Auth Token</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 40 characters</desc>
        </descriptions>
        <length>40</length>
      </constraints>
      <required>true</required>
      <password>true</password>
    </field>
  </dataFields>
</descriptor>
"""

# http://glance.openstack.org/client.html
# http://pypi.python.org/pypi/python-novaclient
class ConsolidatedClient(object):
    def __init__(self, nova_client, glance_client):
        self.nova = nova_client
        self.glance = glance_client

class OpenStackClient(baseDriver.BaseDriver):
    Image = OpenStack_Image
    cloudType = 'openstack'

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData

    RBUILDER_BUILD_TYPE = 'XEN_OVA'  # TODO: Determine appropriate rBuilder image type
    # This should probably be the KVM Raw....

    NovaClientClass = NovaClient
    GlanceClientClass = None

    @classmethod
    def isDriverFunctional(cls):
        return (cls.NovaClientClass is not None)

    # Right now 1.1 is the only version that is supported
    def _openstack_api_version(self):
        return 'v1.1'

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        server = cloudConfig['name']
        port = cloudConfig['nova_port']
        #glance_server = cloudConfig['glance_server']
        #glance_port = cloudConfig['glance_port']
        api_version = self._openstack_api_version()
        authUrl = "http://%s:%s/%s/" % (server, port, api_version)
        try:
            # password is a ProtectedString, we have to convert to string
            novaClient = self.NovaClientClass(credentials['username'],
                                    credentials['auth_token'],
                                    project_id=None,
                                    auth_url=authUrl)
#            glance_client = Client(glance_server, glance_port)
            glanceClient = None
            clients = ConsolidatedClient(novaClient, glanceClient)
        except Exception, e:
            raise errors.PermissionDenied(message =
                    "Error initializing client: %s" % (e, ))
        return clients

    def drvVerifyCloudConfiguration(self, config):
        return

    def terminateInstances(self, instanceIds):
        running_instances = self.getInstances(instanceIds)
        for server in running_instances:
            server.delete() # there is no terminate method in novaclient

        insts = instances.BaseInstances()
        insts.extend(running_instances)
        # Set state
        for inst in insts:
            inst.setState("Terminating")
        return insts

    def terminateInstance(self, instanceId):
        return self.terminateInstances([instanceId])

    def _get_flavors(self):
        client = self.client.nova
        return client.flavors.list()

    # TODO: figure this out.  It is an option launch param.
    def _get_ipgroups(self):
        client = self.client.nova
        return client.ipgroup.list()

    # This also takes optional "ipgroup", "meta", and "files", 
    # see novaclient/servers.py, ignoring for now.  TODO: really ignore?
    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName("OpenStack Launch Parameters")
        descr.addDescription("OpenStack Launch Parameters")
        self.drvLaunchDescriptorCommonFields(descr)
        flavors = self._get_flavors()
        if not flavors:
            raise errors.CatalogError("No instance flavors defined")
        flavor_id_name_map = dict( (f.id, f.name) for f in flavors)
        flavor_id_name_map.keys().sort()
        descr.addDataField("flavor",
            descriptions = "Flavor",
            required = True,
            help = [
                ("launch/flavors.html", None)
            ],
            type = descr.EnumeratedType(
                descr.ValueWithDescription(id, descriptions = flavor_id_name_map[id])
                for x in flavor_id_name_map.keys()),
            default = flavor_id_name_map.keys()[0],
            )

        return descr

    # TODO: remove when novaclient has caught up to v1.1.
    # This pulls a resource id from from a resource ref url
    def _get_id_from_ref(self, resource_ref):
        return resource_ref.split('/')[-1]

    @classmethod
    def _idFromRef(cls, ref):
        if ref is None:
            return ref
        if isinstance(ref, int):
            return str(ref)
        # Grab the last part of the URL and return it
        return os.path.basename(ref)

    def drvGetInstances(self, instanceIds):
        client = self.client.nova
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        images = self.getAllImages()
        # Hash images so we can quickly return a ref
        imagesMap = dict((self._idFromRef(image.opaqueId), image)
            for image in images if hasattr(image, 'opaqueId'))
        for server in client.servers.list():
            instanceId = str(server.id)
            imageRef = self._idFromRef(server.imageRef)
            image = imagesMap.get(imageRef)
            if image:
                imageId = image.id
            else:
                imageId = None
            publicDnsName = None # XXX FIXME
            privateDnsName = None # XXX FIXME
            inst = self._nodeFactory.newInstance(id = instanceId,
                imageId = imageId,
                instanceId = instanceId,
                instanceName = server.name,
                instanceDescription = server.name,
                dnsName = 'UNKNOWN',
                publicDnsName = publicDnsName,
                privateDnsName = privateDnsName,
                state = server.status,
                launchTime = server.created if hasattr(server, 'created') else None,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            instanceList.append(inst)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))
        return self.filterInstances(instanceIds, instanceList)

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        getField = descriptorData.getField
        srUuid = getField('storageRepository')
        params['srUuid'] = srUuid
        return params


    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')

        cloudConfig = self.getTargetConfiguration()
        nameLabel = image.getLongName()
        nameDescription = image.getBuildDescription()

        self._deployImage(job, image, auth)

        imageId = image.getInternalTargetId()

        job.addHistoryEntry('Cloning template')
        realId = self.cloneTemplate(job, imageId, instanceName,
            instanceDescription)
        job.addHistoryEntry('Attaching credentials')
        try:
            self._attachCredentials(realId)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        job.addHistoryEntry('Launching')
        self.startVm(realId)
        return self.client.xenapi.VM.get_uuid(realId)

    def getImagesFromTarget(self, imageIdsFilter):
        cloudAlias = self.getCloudAlias()

        client = self.client.nova
        ret = []
        for image in client.images.list(detailed=True):
            # image.id is numeric
            imageId = str(image.id)
            imageName = image.name
            img = self._nodeFactory.newImage(
                id = imageId,
                imageId = imageId,
                isDeployed = True,
                is_rBuilderImage = False,
                shortName = imageName,
                productName = imageName,
                longName = imageName,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)
            img.opaqueId = self._getLinkRel(image, 'self')
            ret.append(img)
        return ret

    @classmethod
    def _getLinkRel(cls, obj, rel):
        for link in obj.links:
            if link['rel'] == rel:
                return link['href']
        return None

    def startVm(self, name, imageRef, flavorRef):
        client = self.client.nova
        server = client.create(name, imageRef, flavorRef) # ipGroup, etc
