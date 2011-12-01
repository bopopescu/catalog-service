#
# Copyright (c) 2008 rPath, Inc.  All Rights Reserved.
#

import operator
import os
import StringIO
import tarfile
import tempfile

from conary.lib import util

from catalogService import errors
from catalogService import storage
from catalogService.rest import baseDriver
from catalogService.rest.models import clouds
from catalogService.rest.models import images
from catalogService.rest.models import instances
from catalogService.libs.viclient.VimService_client import *  # pyflakes=ignore

_configurationDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>VMware Configuration</displayName>
    <descriptions>
      <desc>Configure VMware</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>name</name>
      <descriptions>
        <desc>Server Address</desc>
      </descriptions>
      <type>str</type>
      <required>true</required>
      <help href='configuration/serverName.html'/>
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

_credentialsDescriptorXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>VMware User Credentials</displayName>
    <descriptions>
      <desc>User Credentials for VMware</desc>
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
        <length>32</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>password</name>
      <descriptions>
        <desc>Password</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 32 characters</desc>
        </descriptions>
        <length>32</length>
      </constraints>
      <required>true</required>
      <password>true</password>
    </field>
  </dataFields>
</descriptor>
"""

_systemCaptureXmlData = """<?xml version='1.0' encoding='UTF-8'?>
<descriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.rpath.org/permanent/descriptor-1.0.xsd descriptor-1.0.xsd">
  <metadata>
    <displayName>VMware System Capture</displayName>
    <descriptions>
      <desc>Capturing a System's Image</desc>
    </descriptions>
  </metadata>
  <dataFields>
    <field>
      <name>instanceId</name>
      <descriptions>
        <desc>System ID</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must contain between 1 and 36 characters</desc>
        </descriptions>
        <length>36</length>
      </constraints>
      <required>true</required>
      <hidden>true</hidden>
    </field>
    <field>
      <name>imageTitle</name>
      <descriptions>
        <desc>Image Title</desc>
      </descriptions>
      <type>str</type>
      <constraints>
        <descriptions>
          <desc>Field must be between 1 and 64 characters</desc>
        </descriptions>
        <length>64</length>
      </constraints>
      <required>true</required>
    </field>
    <field>
      <name>architecture</name>
      <descriptions>
        <desc>Architecture</desc>
      </descriptions>
      <help lang="en_US" href="@Help_import_image_arch@"/>
      <enumeratedType>
        <describedValue>
          <descriptions>
            <desc>x86</desc>
          </descriptions>
          <key>x86</key>
        </describedValue>
        <describedValue>
          <descriptions>
            <desc>x86_64</desc>
          </descriptions>
          <key>x86_64</key>
        </describedValue>
      </enumeratedType>
      <required>true</required>
    </field>
  </dataFields>
</descriptor>
"""


class VMwareImage(images.BaseImage):
    'VMware Image'

def formatSize(size):
    suffixes = (' bytes', ' KiB', ' MiB', ' GiB')
    div = 1
    for suffix in suffixes:
        if size < (div * 1024):
            return '%d %s' %(size / div, suffix)
        div = div * 1024
    return '%d TiB' %(size / div)

class InstanceStorage(storage.DiskStorage):
    """
    VMware instance ids should look like a UUID
    """
    @classmethod
    def _generateString(cls, length):
        return baseDriver.BaseDriver.uuidgen()

class VMwareClient(baseDriver.BaseDriver):
    Image = VMwareImage
    cloudType = 'vmware'
    instanceStorageClass = InstanceStorage

    configurationDescriptorXmlData = _configurationDescriptorXmlData
    credentialsDescriptorXmlData = _credentialsDescriptorXmlData
    systemCaptureXmlData = _systemCaptureXmlData
    # transport is mocked out during testing to simulate talking to
    # an actual server
    VimServiceTransport = None

    RBUILDER_BUILD_TYPE = 'VMWARE_ESX_IMAGE'
    # We should prefer OVA over OVF, but vcenter gets upset with
    # gzip-compressed vmdk images inside ova
    #OVF_PREFERRENCE_LIST = [ '.ova', 'ovf.tar.gz', ]
    OVF_PREFERRENCE_LIST = [ 'ovf.tar.gz', 'ova', ]

    def __init__(self, *args, **kwargs):
        baseDriver.BaseDriver.__init__(self, *args, **kwargs)
        self._vicfg = None
        self._virtualMachines = None

    def drvCreateCloudClient(self, credentials):
        cloudConfig = self.getTargetConfiguration()
        host = self.cloudName
        # This import is expensive!!! Delay it until it is actually needed
        from catalogService.libs import viclient
        debug = False
        #debug = True
        try:
            client = viclient.VimService(host,
                                         credentials['username'],
                                         credentials['password'],
                                         transport=self.VimServiceTransport,
                                         debug = debug)
        except Exception, e:
            # FIXME: better error
            raise errors.PermissionDenied(message = '')
        return client

    def _getVIConfig(self):
        if self._vicfg is None:
            self._vicfg = self.client.getVIConfig()
        return self._vicfg
    vicfg = property(_getVIConfig)

    def getDeployImageParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getDeployImageParameters(self,
            image, descriptorData)
        self._paramsFromDescriptorData(params, descriptorData)
        return params

    def getLaunchInstanceParameters(self, image, descriptorData):
        params = baseDriver.BaseDriver.getLaunchInstanceParameters(self,
            image, descriptorData)
        self._paramsFromDescriptorData(params, descriptorData)
        return params

    def _paramsFromDescriptorData(self, params, descriptorData):
        getField = descriptorData.getField
        dataCenter = getField('dataCenter')
        cr = getField('cr-%s' % dataCenter)
        rp = getField('resourcePool-%s' % cr)
        network = getField('network-%s' % dataCenter)
        folder = getField('vmfolder-%s' % dataCenter)
        params.update(dict(
            dataCenter = dataCenter,
            dataStore = getField('dataStore-%s' % cr),
            computeResource = cr,
            resourcePool = rp,
            network = network,
            vmFolder=folder,
        ))
        return params

    def drvPopulateImageDeploymentDescriptor(self, descr):
        descr.setDisplayName('VMware Image Upload Parameters')
        descr.addDescription('VMware Image Upload Parameters')
        self.drvImageDeploymentDescriptorCommonFields(descr)
        return self._drvPopulateDescriptorFromTarget(descr)

    def drvPopulateLaunchDescriptor(self, descr):
        descr.setDisplayName('VMware Launch Parameters')
        descr.addDescription('VMware Launch Parameters')
        self.drvLaunchDescriptorCommonFields(descr)
        return self._drvPopulateDescriptorFromTarget(descr)

    def _drvPopulateDescriptorFromTarget(self, descr):
        vicfg = self.vicfg
        dataCenters = [ x for x in vicfg.getDatacenters()
            if x.getComputeResources() ]
        descr.addDataField('dataCenter',
                           descriptions = 'Data Center',
                           required = True,
                           help = [
                               ('launch/dataCenter.html', None)
                           ],
                           type = descr.EnumeratedType(
            descr.ValueWithDescription(x.obj,
                                            descriptions=x.properties['name'])
            for x in dataCenters),
                           default = dataCenters[0].obj,
                           )
        crToDc = {}
        validDatacenters = []
        for dc in dataCenters:
            crs = dc.getComputeResources()
            validCrs = {}
            for cr in crs:
                cfg = cr.configTarget
                if cfg is None:
                    continue
                validCrs[cr] = dc
            if not validCrs:
                continue
            crToDc.update(validCrs)
            validDatacenters.append(dc)

            folders = vicfg.getVmFolderLabelsForTree(dc.properties['vmFolder'])

            descr.addDataField('vmfolder-%s' % dc.obj,
                descriptions = "VM Folder",
                required = True,
                help = [ ('launch/vmfolder.html', None) ],
                type = descr.EnumeratedType(
                    descr.ValueWithDescription(
                        x[1], descriptions=x[0])
                    for x in folders),
                   default = folders[0][1],
                   conditional = descr.Conditional(
                        fieldName='dataCenter',
                        operator='eq',
                        fieldValue=dc.obj)
                    )

            descr.addDataField('cr-%s' %dc.obj,
                               descriptions = 'Compute Resource',
                               required = True,
                               help = [
                                   ('launch/computeResource.html', None)
                               ],
                               type = descr.EnumeratedType(
                descr.ValueWithDescription(
                x.obj, descriptions=x.properties['name'])
                for x in crs),
                               default = crs[0].obj,
                               conditional = descr.Conditional(
                                    fieldName='dataCenter',
                                    operator='eq',
                                    fieldValue=dc.obj)
                               )

        for dc in validDatacenters:
            # We may have references to invalid networks, skip those
            networks = dc.properties['network']
            networks = [ vicfg.getNetwork(x) for x in networks ]
            networks = [ x for x in networks if x is not None ]
            descr.addDataField('network-%s' % dc.obj,
                descriptions = 'Network',
                required = True,
                    help = [
                        ('launch/network.html', None)
                    ],
                    type = descr.EnumeratedType(
                        descr.ValueWithDescription(x.mor,
                            descriptions=x.name) for x in networks),
                    default = networks[0].mor,
                    conditional = descr.Conditional(
                        fieldName='dataCenter',
                        operator='eq',
                        fieldValue=dc.obj))

        for cr, dc in crToDc.items():
            cfg = cr.configTarget
            dataStores = []

            for ds in cfg.get_element_datastore():
                if hasattr(ds, '_mode') and ds.get_element_mode() == 'readOnly':
                    # Read-only datastore. Can't launch on it
                    continue
                name = ds.get_element_name()
                dsInfo = ds.get_element_datastore()
                free = dsInfo.get_element_freeSpace()
                dsDesc = '%s - %s free' %(name, formatSize(free))
                dsMor = ds.get_element_datastore().get_element_datastore()
                dataStores.append((dsMor, dsDesc))
            descr.addDataField('dataStore-%s' %cr.obj,
                               descriptions = 'Data Store',
                               required = True,
                               help = [
                                   ('launch/dataStore.html', None)
                               ],
                               type = descr.EnumeratedType(
                descr.ValueWithDescription(x[0], descriptions = x[1])
                for x in dataStores),
                               default = dataStores[0][0],
                               conditional = descr.Conditional(
                                    fieldName='cr-%s' %dc.obj,
                                    operator='eq',
                                    fieldValue=cr.obj)
                               )
            # FIXME: add (descr.Conditional(
            #fieldName='dataCenter',
            #    operator='eq',
            #    fieldValue=dc.obj),

        for cr, dc in crToDc.items():
            # sort a list of mor, name tuples based on name
            # and use the first tuple's mor as the default resource pool
            defaultRp = sorted(((x[0], x[1]['name'])
                                for x in cr.resourcePools.iteritems()),
                               key=operator.itemgetter(1))[0][0]
            descr.addDataField('resourcePool-%s' %cr.obj,
                               descriptions = 'Resource Pool',
                               required = True,
                               help = [
                                   ('launch/resourcePool.html', None)
                               ],
                               type = descr.EnumeratedType(
                descr.ValueWithDescription(str(x[0]),
                                                descriptions=x[1]['name'])
                for x in cr.resourcePools.iteritems()),
                               default = defaultRp,
                               conditional = descr.Conditional(
                                    fieldName='cr-%s' %dc.obj,
                                    operator='eq',
                                    fieldValue=cr.obj)
                               )

        return descr

    def postFork(self):
        if self._cloudClient is not None:
            # Pretend that we're not logged in, otherwise the __del__ method
            # will log out the parent
            self._cloudClient._loggedIn = False
        return baseDriver.BaseDriver.postFork(self)

    def terminateInstances(self, instanceIds):
        insts = self.getInstances(instanceIds)
        for instanceId in instanceIds:
            self.client.shutdownVM(uuid=instanceId)
        for inst in insts:
            inst.setState('Terminating')
        return insts

    def terminateInstance(self, instanceId):
        # FIXME: re-factor this into common code (copied from Xen Ent)
        return self.terminateInstances([instanceId])

    def _getMintImagesByType(self, imageType):
        # start with the most general build type
        imageType = 'VMWARE_ESX_IMAGE'
        mintImages = self.db.imageMgr.getAllImagesByType(imageType)
        if self.client.vmwareVersion < (4, 0, 0):
            # We don't support OVF deployments, so don't even bother
            return mintImages
        # Prefer ova (ovf 1.0) over ovf 0.9 over plain esx
        mintImagesByBuildId = {}
        for mintImage in mintImages:
            files = self._getPreferredOvfImage(mintImage['files'])
            if files:
                mintImage['files'] = files
            mintImagesByBuildId[mintImage['buildId']] = mintImage
        # Finally, prefer OVF 1.0 images (unused at the moment)
        imageType = 'VMWARE_OVF_IMAGE'
        for mintImage in self.db.imageMgr.getAllImagesByType(imageType):
            mintImagesByBuildId[mintImage['buildId']] = mintImage
        # Sort data by build id
        return [ x[1] for x in sorted(mintImagesByBuildId.items()) ]

    @classmethod
    def _getPreferredOvfImage(cls, files):
        for suffix in cls.OVF_PREFERRENCE_LIST:
            for fdict in files:
                fname = fdict.get('fileName', '')
                if fname.endswith(suffix):
                    return [ fdict ]
        return None

    def _buildInstanceList(self, instanceList, instMap):
        instIdSet = set()
        newInstanceList = []
        cloudAlias = self.getCloudAlias()
        for mor, vminfo in instMap.iteritems():
            if vminfo.get('config.template', False):
                continue
            if not 'config.uuid' in vminfo:
                continue
            launchTime = None
            if 'runtime.bootTime' in vminfo:
                launchTime = self.utctime(vminfo['runtime.bootTime'])
            instanceId = vminfo['config.uuid']
            longName = vminfo.get('config.annotation', '').decode('utf-8', 'replace')
            inst = self._nodeFactory.newInstance(
                id = instanceId,
                instanceName = vminfo['name'],
                instanceDescription = longName,
                instanceId = instanceId,
                reservationId = instanceId,
                dnsName = vminfo.get('guest.ipAddress', None),
                publicDnsName = vminfo.get('guest.ipAddress', None),
                state = vminfo['runtime.powerState'],
                launchTime = launchTime,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)

            inst._opaqueId = mor

            instIdSet.add(instanceId)
            newInstanceList.append(inst)
        # Add back the original instances, unless we have them already
        for inst in instanceList:
            instanceId = inst.getInstanceId()
            if instanceId in instIdSet:
                continue
            instIdSet.add(instanceId)
            newInstanceList.append(inst)

        del instanceList[:]
        instanceList.extend(newInstanceList)
        instanceList.sort(key = lambda x: (x.getState(), x.getInstanceId()))

        return instanceList

    def drvGetInstance(self, instanceId):
        uuidRef = self.client.findVMByUUID(instanceId)
        if not uuidRef:
            raise errors.HttpNotFound()

        instMap = self._getVirtualMachines(root = uuidRef)
        instanceList = instances.BaseInstances()

        ret = self._buildInstanceList(instanceList, instMap)
        if ret:
            return ret[0]
        raise errors.HttpNotFound()

    def drvGetInstances(self, instanceIds, force=False):
        cloudAlias = self.getCloudAlias()
        instanceList = instances.BaseInstances()
        instMap = self.getVirtualMachines(force=force)
        return self.filterInstances(instanceIds,
            self._buildInstanceList(instanceList, instMap))

    def getVirtualMachines(self, force=False):
        if self._virtualMachines is not None and not force:
            # NOTE: we cache this, but only per catalog-service request.
            # Each request generates a new Client instance.
            return self._virtualMachines

        instMap = self._getVirtualMachines()
        self._virtualMachines = instMap
        return instMap

    def _getVirtualMachines(self, root = None):
        instMap = self.client.getVirtualMachines([ 'name',
                                                   'config.annotation',
                                                   'config.template',
                                                   'runtime.powerState',
                                                   'runtime.bootTime',
                                                   'config.uuid',
                                  # NOTE: grabbing extra
                                  # config multiplies the
                                  # size of the XML being
                                  # returned by 5 and should
                                  # not be done without
                                  # some sort of delayed parsing scheme.
                                                   #'config.extraConfig',
                                                   'guest.ipAddress' ],
                                                   root = root)
        return instMap

    def drvCaptureSystem(self, job, instance, params):
        vmMor = instance._opaqueId
        vmName = instance.getInstanceName()
        tmpVmName = self._getCaptureTmpName(vmName)
        # Optional params
        dcMor = params.get('datacenterMor')
        resourcePoolMor = params.get('resourcePoolMor')
        dataStoreMor = params.get('dataStoreMor')
        folderMor = params.get('folderMor')
        callback = self.taskCallbackFactory(job, "Cloning: %d%%")
        cloneMor = self.client.cloneVM(mor=vmMor, name=tmpVmName,
            dc=dcMor, rp=resourcePoolMor, ds=dataStoreMor, callback=callback)

        progressUpdate = self.LeaseProgressUpdate(httpNfcLease,
            callback=callback)

        destDir = tempfile.mkdtemp(prefix="system-capture-%s" % self.cloudType)
        try:
            callback = lambda x: self._msg(job, "Exporting OVF: %d%% complete" % x)
            self._msg(job, "Exporting VM %s" % tmpVmName)
            ovfFiles = self.client.ovfExport(cloneMor, vmName, destDir, progressUpdate)
            archive = self._buildExportArchive(job, destDir, ovfFiles)
            return archive
        finally:
            self._msg(job, "Destroying VM %s" % tmpVmName)
            callback = self.taskCallbackFactory(job, "Destroying VM: %d%%")
            self.client.destroyVM(cloneMor, callback=callback)
            util.rmtree(destDir, ignore_errors=True)

    @classmethod
    def getImageIdFromMintImage(cls, image, targetImageIds):
        imageSha1 = baseDriver.BaseDriver.getImageIdFromMintImage(image,
            targetImageIds)
        if imageSha1 is None:
            return imageSha1
        if isinstance(imageSha1, int):
            # fake the image sha1
            imageSha1 = "%032x" % imageSha1
        return cls._uuid(imageSha1)

    def getImagesFromTarget(self, imageIds):
        """
        returns all templates in the inventory
        currently we return the templates as available images
        """
        useTemplate = not self.client.isESX()
        if not useTemplate:
            # ESX does not support templates, so don't bother to search
            # for them
            return []
        cloudAlias = self.getCloudAlias()
        instMap = self.getVirtualMachines()
        imageList = images.BaseImages()
        for opaqueId, vminfo in instMap.items():
            if not vminfo.get('config.template', False):
                continue

            imageId = vminfo['config.uuid']
            templateId = self._extractRbaUUID(vminfo.get('config.annotation'))
            if imageIds is not None and not (
                    imageId in imageIds or templateId in imageIds):
                continue
            if templateId:
                longName = vminfo['name']
                imageId = templateId
            else:
                longName = vminfo.get('config.annotation', '').decode('utf-8', 'replace')
            image = self._nodeFactory.newImage(
                id = imageId,
                imageId = imageId,
                isDeployed = True,
                is_rBuilderImage = False,
                shortName = vminfo['name'],
                productName = vminfo['name'],
                internalTargetId = vminfo['config.uuid'],
                longName = longName,
                cloudName = self.cloudName,
                cloudAlias = cloudAlias)
            # This is a bit nasty, but we need the opaque ID later when
            # launching, so we clone the proper image (instead of the one with
            # the image ID possibly coming from the rbuilder)
            image.opaqueId = opaqueId
            imageList.append(image)
        return imageList

    def _extractRbaUUID(self, annotation):
        # Extract the rbuilder uuid from the annotation field
        if not annotation:
            return None
        sio = StringIO.StringIO(annotation)
        for r in sio:
            arr = r.strip().split(':', 1)
            if len(arr) != 2:
                continue
            if arr[0].strip().lower() == 'rba-uuid':
                return arr[1].strip().lower()
        return None

    def _cloneTemplate(self, job, imageId, instanceName, instanceDescription,
                       dataCenter, computeResource, dataStore,
                       resourcePool, vm=None, vmFolder=None, callback=None):
        templateUuid = None
        if not vm:
            templateUuid = os.path.basename(imageId)
        try:
            vmMor = self.client.cloneVM(mor=vm,
                                        uuid=templateUuid,
                                        name=instanceName,
                                        annotation=instanceDescription,
                                        dc=self.vicfg.getMOR(dataCenter),
                                        ds=self.vicfg.getMOR(dataStore),
                                        rp=self.vicfg.getMOR(resourcePool),
                                        vmFolder=self.vicfg.getMOR(vmFolder),
                                        callback=callback)
            return vmMor
        except Exception, e:
            self.log_exception("Exception cloning template: %s" % e)
            raise

    def _findUniqueName(self, inventoryPrefix, startName):
        # make sure that the vm name is not used in the inventory
        testName = startName
        x = 0
        while True:
            ret = self.client.findVMByInventoryPath(inventoryPrefix + testName)
            if not ret:
                # the name is not used in the inventory, stop looking
                break
            x += 1
            # add a suffix to make it unique
            testName = startName + '-%d' %x
        return testName

    def _deployOvf(self, job, vmName, uuid, archive, dataCenter,
                     dataStore, host, resourcePool, network,
                     vmFolder=None,
                     asTemplate = False):
        # Grab ovf file
        ovfFiles = list(archive.iterFileWithExtensions(['.ovf']))
        if not ovfFiles:
            raise RuntimeError("No ovf file found")
        if len(ovfFiles) != 1:
            raise RuntimeError("More than one .ovf file found")
        ovfFileMember = ovfFiles[0]
        ovfFileObj = archive.extractfile(ovfFileMember)
        archive.baseDir = os.path.dirname(ovfFileMember.name)

        if vmFolder is None:
            vmFolder = dataCenter.properties['vmFolder']
        self._msg(job, 'Importing OVF descriptor')

        from ZSI import FaultException
        msg =  'The object has already been deleted or has not been completely created'
        for i in range(5):
            try:
                return self._uploadOvf_1(job, ovfFileObj, archive, vmName,
                    vmFolder, resourcePool, dataStore, network)
            except FaultException, e:
                if e.fault.string != msg:
                    raise
                self._msg(job, 'Import failed, retrying...')
        else: # for
            # We failed repeatedly. Give up.
            raise

    def _uploadOvf_1(self, job, ovfFileObj, archive, vmName, vmFolder,
                     resourcePool, dataStore, network):
        fileItems, httpNfcLease = self.client.ovfImportStart(ovfFileObj,
            vmName = vmName, vmFolder = vmFolder, resourcePool = resourcePool,
            dataStore = dataStore, network = network)
        self.client.waitForLeaseReady(httpNfcLease)

        callback = lambda x: self._msg(job, "Importing OVF: %d%% complete" % x)
        progressUpdate = self.LeaseProgressUpdate(httpNfcLease,
            callback=callback)

        vmMor = self.client.ovfUpload(httpNfcLease, archive, fileItems,
            progressUpdate)
        return vmMor

    def _deployByVmx(self, job, vmName, uuid, archive, dataCenter,
                     dataStoreName, host, resourcePool, network,
                     asTemplate = False):
        dataCenterName = dataCenter.properties['name']
        from catalogService.libs import viclient
        vmx = viclient.vmutils.uploadVMFiles(self.client,
                                             archive,
                                             vmName,
                                             dataCenter=dataCenterName,
                                             dataStore=dataStoreName)
        try:
            self._msg(job, 'Registering VM')
            vm = self.client.registerVM(dataCenter.properties['vmFolder'], vmx,
                                        vmName, asTemplate=False,
                                        host=host, pool=resourcePool)
            return vm
        except viclient.Error, e:
            self.log_exception("Exception registering VM: %s", e)
            raise RuntimeError('An error occurred when registering the '
                               'VM: %s' %str(e))

    def getImageIdFromTargetImageRef(self, vmRef):
        return self._getVmUuid(vmRef)

    def _deployImageFromFile(self, job, image, filePath, dataCenter,
                             dataStore, computeResource, resourcePool, vmName,
                             uuid, network, vmFolder=None, asTemplate=False):

        logger = lambda *x: self._msg(job, *x)
        dc = self.vicfg.getDatacenter(dataCenter)
        dcName = dc.properties['name']

        cr = dc.getComputeResource(computeResource)
        ds = self.vicfg.getMOR(dataStore)
        dsInfo = self.client.getDynamicProperty(ds, 'summary')
        dsName = dsInfo.get_element_name()
        rp = self.vicfg.getMOR(resourcePool)
        network = self.vicfg.getMOR(network)
        props = self.vicfg.getProperties()
        # find a host that can access the datastore
        hosts = [ x for x in cr.properties['host'] if ds in props[x]['datastore'] ]
        if not hosts:
            raise RuntimeError('no host can access the requested datastore')
        host = hosts[0]

        if vmFolder is None:
            vmFolderMor = dc.properties['vmFolder']
        else:
            vmFolderMor = self.vicfg.getMOR(vmFolder)
        dcName_, vmFolderPath = self.vicfg.getVmFolderLabelPath(vmFolderMor)
        if dcName_ is None:
            # Requested a folder with no path to the top level
            raise errors.ParameterError()
        inventoryPrefix = '/%s/%s/' %(dcName_, vmFolderPath)
        vmName = self._findUniqueName(inventoryPrefix, vmName)
        # FIXME: make sure that there isn't something in the way on
        # the data store

        fileExtensions = [ '.ovf', '.vmx' ]
        try:
            archive = self.Archive(filePath, logger)
            archive.extract()
            vmFiles = list(archive.iterFileWithExtensions(fileExtensions))
            if not vmFiles:
                raise RuntimeError("No file(s) found: %s" %
                    ', '.join("*%s" % x for x in fileExtensions))
            self._msg(job, 'Uploading image to VMware')
            if self.client.vmwareVersion >= (4, 0, 0):
                vmMor = self._deployOvf(job, vmName, uuid,
                    archive, dc, dataStore=ds,
                    host = host, resourcePool=rp, network = network,
                    vmFolder=vmFolderMor,
                    asTemplate = asTemplate)
            else:
                vmMor = self._deployByVmx(job, vmName, uuid,
                    archive, dc, dataStoreName=dsName,
                    host = host, resourcePool=rp, network = network,
                    asTemplate = asTemplate)

            nwobj = self.client.getMoRefProp(vmMor, 'network')
            reconfigVmParams = dict()
            if not nwobj.get_element_ManagedObjectReference():
                # add NIC
                nicSpec = self.client.createNicConfigSpec(network, self._vicfg)
                deviceChange = [ nicSpec ]
                reconfigVmParams['deviceChange'] = deviceChange

            if asTemplate:
                # Reconfiguring the uuid is unreliable, we're using the
                # annotation field for now
                reconfigVmParams['annotation'] = "rba-uuid: %s" % uuid

            if reconfigVmParams:
                self._msg(job, 'Reconfiguring VM')
                self.client.reconfigVM(vmMor, reconfigVmParams)

            if asTemplate:
                self._msg(job, 'Converting VM to template')
                self.client.markAsTemplate(vm=vmMor)
            image.setShortName(vmName)
            return vmMor
        finally:
            pass

    def _getVmUuid(self, vmMor):
        # Grab the real uuid
        instMap = self.client.getVirtualMachines(['config.uuid' ], root = vmMor)

        uuid = instMap[vmMor]['config.uuid']
        return uuid

    def deployImageProcess(self, job, image, auth, **params):
        if image.getIsDeployed():
            self._msg(job, "Image is already deployed")
            return image.getImageId()

        ppop = params.pop
        dataCenter = ppop('dataCenter')
        computeResource = ppop('computeResource')
        dataStore = ppop('dataStore')
        resourcePool= ppop('resourcePool')
        imageName = ppop('imageName')
        network = ppop('network')
        vmFolder = ppop('vmFolder')

        newImageId = self.instanceStorageClass._generateString(32)
        useTemplate = not self.client.isESX()

        if useTemplate:
            # if we can use a template, deploy the image
            # as a template with the imageId as the uuid
            vmName = 'template-' + image.getBaseFileName()
            uuid = image.getImageId()
        else:
            # otherwise, we'll use the instance name and
            # a random instance uuid for deployment
            vmName = imageName
            uuid = newImageId

        vm = self._deployImage(job, image, auth, dataCenter,
                               dataStore, computeResource,
                               resourcePool, vmName, uuid, network,
                               vmFolder=vmFolder, asTemplate = useTemplate)
        self._msg(job, 'Image deployed')
        return image.getImageId()

    def taskCallbackFactory(self, job, message):
        def callback(values):
            status, progress, error = values
            if status != "running" or not isinstance(progress, int):
                return
            self._msg(job, message % progress)
        return callback

    class ProgressUpdate(baseDriver.BaseDriver.IntervalCallback):
        INTERVAL = 5

    def LeaseProgressUpdate(self, lease, callback):
        from catalogService.libs.viclient import client
        progress = client.LeaseProgressUpdate(self.client._service, lease, callback)
        return self.ProgressUpdate(totalSize=0, callback=progress.progress)

    def launchInstanceProcess(self, job, image, auth, **launchParams):
        ppop = launchParams.pop
        imageId = ppop('imageId')
        dataCenter = ppop('dataCenter')
        computeResource = ppop('computeResource')
        dataStore = ppop('dataStore')
        resourcePool= ppop('resourcePool')
        instanceName = ppop('instanceName')
        instanceDescription = ppop('instanceDescription')
        network = ppop('network')
        vmFolder = ppop('vmFolder')

        vm = None

        instanceId = self.instanceStorageClass._generateString(32)
        useTemplate = not self.client.isESX()
        if not image.getIsDeployed():
            if useTemplate:
                # if we can use a template, deploy the image
                # as a template with the imageId as the uuid
                vmName = 'template-' + image.getBaseFileName()
                uuid = image.getImageId()
            else:
                # otherwise, we'll use the instance name and
                # a random instance uuid for deployment
                vmName = instanceName
                uuid = instanceId
            vm = self._deployImage(job, image, auth, dataCenter,
                                   dataStore, computeResource,
                                   resourcePool, vmName, uuid,
                                   network, vmFolder=vmFolder,
                                   asTemplate = useTemplate)
        else:
            # Since we're bypassing _getTemplatesFromInventory, none of the
            # images should be marked as deployed for ESX targets
            assert useTemplate
            vm = getattr(image, 'opaqueId')

        if useTemplate:
            self._msg(job, 'Cloning template')
            cloneCallback = self.taskCallbackFactory(job, "Cloning: %d%%")

            vmMor = self._cloneTemplate(job, image.getImageId(), instanceName,
                                        instanceDescription,
                                        dataCenter, computeResource,
                                        dataStore, resourcePool, vm=vm,
                                        vmFolder=vmFolder,
                                        callback=cloneCallback)
        else:
            vmMor = self.client._getVM(mor=vm)

        try:
            self._attachCredentials(job, instanceName, vmMor, dataCenter, dataStore,
                                    computeResource)
        except Exception, e:
            self.log_exception("Exception attaching credentials: %s" % e)
        self._msg(job, 'Launching')
        self.client.startVM(mor = vmMor)
        uuid = self._getVmUuid(vmMor)
        self._msg(job, 'Instance launched')
        return uuid

    def _attachCredentials(self, job, vmName, vmMor, dataCenterMor, dataStoreMor,
            computeResourceMor):
        filename = self.getCredentialsIsoFile()
        dataCenter = self.vicfg.getDatacenter(dataCenterMor).properties['name']
        dsInfo = self.vicfg.getMOR(dataStoreMor)
        dataStore = self.client.getDynamicProperty(dsInfo, 'summary').get_element_name()
        from catalogService.libs import viclient
        try:
            self._msg(job, 'Uploading initial configuration')
            fileobj = baseDriver.Archive.CommandArchive.File(
                os.path.basename(filename), os.path.dirname(filename))
            viclient.vmutils._uploadVMFiles(self.client, [ fileobj ], vmName,
                dataCenter = dataCenter, dataStore = dataStore)
        finally:
            # We use filename below only for the actual name; no need to keep
            # this file around now
            os.unlink(filename)

        dc = self.vicfg.getMOR(dataCenterMor)
        hostFolder = self.client.getMoRefProp(dc, 'hostFolder')
        hostMor = self.client.getFirstDecendentMoRef(hostFolder, 'HostSystem')
        cr = self.vicfg.getMOR(computeResourceMor)
        defaultDevices = self.client.getDefaultDevices(cr, hostMor)

        datastoreVolume = self.client._getVolumeName(dataStore)
        controllerMor = self.client._getIdeController(defaultDevices)
        try:
            self._msg(job, 'Creating initial configuration disc')
            cdromSpec = self.client.createCdromConfigSpec(
                os.path.basename(filename), vmMor, controllerMor,
                dataStoreMor, datastoreVolume)
            self.client.reconfigVM(vmMor, dict(deviceChange = [ cdromSpec ]))
        except viclient.client.FaultException, e:
            # We will not fail the request if we could not attach credentials
            # to the instance
            self.log_exception("Exception trying to attach credentials: %s", e)


