from conary.lib import util

from catalogService import images, instances

class Image(images.BaseImage):
    "Globus Virtual Workspaces Image"

    __slots__ = images.BaseImage.__slots__ + ['isDeployed', 'buildId',
                                              'downloadUrl', 'buildPageUrl',
                                              'baseFileName']

    def __init__(self, attrs = None, nsMap = None, **kwargs):
        self.downloadUrl = kwargs.pop('downloadUrl')
        self.buildPageUrl = kwargs.pop('buildPageUrl')
        self.baseFileName = kwargs.pop('baseFileName')
        images.BaseImage.__init__(self, attrs = None, nsMap = None, **kwargs)
        self.setIsDeployed(kwargs.get('isDeployed'))
        self.setBuildId(kwargs.get('buildId'))
        self.downloadUrl = downloadUrl


    def setIsDeployed(self, data):
        self.isDeployed = None
        if data is None:
            return self
        data = xmllib.BooleanNode.toString(data)
        self.isDeployed = xmllib.GenericNode().setName('isDeployed').characters(data)
        return self

    def getIsDeployed(self):
        if self.isDeployed is None:
            return None
        return xmllib.BooleanNode.fromString(self.isDeployed.getText())

class Images(images.BaseImages):
    "Globus Virtual Workspaces Images"

class Instance(instances.BaseInstance):
    "Globus Virtual Workspaces Instance"

class Instances(instances.BaseInstances):
    "Globus Virtual Workspaces Instances"

class ImageFactory(object):
    def __init__(self):
        self.linker = instances.Linker()

    def __call__(self, *args, **kw):
        image = Image(*args, **kw)
        image.setId(self.linker.imageUrl(image.getCloudType(),
                                         image.getCloudName(),
                                         image.getId()))
        return image

class Handler(images.Handler):
    imageClass = Image
    imagesClass = Images


class VWSClient(object):
    def __init__(self, cfg, mintClient, instanceFactory, imageFactory):
        self._cfg = cfg
        self._mintClient = mintClient
        self._instanceFactory = instanceFactory
        self._imageFactory = ImageFactory()
        self.instancesDir = '/tmp/catalog-service-instances'
        util.mkdirChain(self.instancesDir)

    def _getCloudClient(self, cloudId):
        if cloudId in self.clients:
            return self.client[cloudId]
        props = globuslib.WorkspaceCloudProperties()
        props.set('vws.factory', cloudCred['factory'])
        props.set('vws.repository', cloudCred['repository'])
        props.set('vws.factory.identity', cloudCred['factoryIdentity'])
        props.set('vws.repository.identity', cloudCred['repositoryIdentity'])
        cli = globuslib.WorkspaceCloudClient(props, cloudCred['caCert'],
            cloudCred['userCert'], cloudCred['userKey'],
            cloudCred['sshPubKey'], cloudCred['alias'])
        self.clients[cloudId] = cli
        return cli

    def cloudParameters(self):
        return CloudParameters()

    def createCloud(self, parameters):
        parameters = CloudParameters(parameters)

    def updateCloud(self, cloudId, parameters):
        parameters = CloudParameters(parameters)
        pass

    def listInstanceIds(self, cloudId):
        self.clients[cloudId].listInstanceIds

    def listImageIds(self, cloudId):
        pass

    def publishImage(self, cloudId, image):
        self.cloudClient.transferInstance(fileName)
        pass

    def launchInstanceParameters(self):
        return LaunchInstanceParameters()

    def launchInstances(self, cloudId, imageIds, parameters):
        pass

    def launchInstance(self, cloudId, xmlString, requestIPAddress):
        parameters = LaunchInstanceParameters(xmlString)
        imageId = parameters.imageId
        image = self.getImage(imageId)
        instanceId = self.instanceStore.newInstance(cloudId, imageId)
        self._daemonize(self._launchInstance,
                        cloudId, imageId, instanceId, image,
                        duration=parameters.duration,
                        instanceType=parameters.instanceType)
        cloudAlias = self.client[cloudId].getCloudAlias()
        instanceList = Instances()
        instance = self.instanceFactory(id=instanceId,
                                        instanceId=instanceId,
                                        imageId=imageId,
                                        cloudName=cloudId,
                                        cloudType='vws',
                                        cloudAlias=cloudAlias)
        instanceList.append(instances)
        return instanceList

    def terminateInstances(self, cloudId, instanceIds):
        self.clients[cloudId].terminateInstances(instanceId)

    def terminateInstance(self, cloudId, instanceId):
        self.client[cloudId].terminateInstances([instanceId])


    def getAllImages(self, cloudId):
        return self.getImages(cloudId, None)

    def getImages(self, cloudId, imageIds):
        imageList = self._getImagesFromGrid()
        imageList = self._addMintDataToImageList(imageList)
        # now that we've grabbed all the images, we can return only the one
        # we want.  This is horribly inefficient.
        if imageIds is not None:
            imagesById = dict((x.getImageId(), x) for x in imageList )
            newImageList = []
            for imageId in imageIds:
                if imageId.endswith('.gz') and imageId not in imagesById:
                    imageId = imageId[:-3]
                newImageList.append(imagesById[imageId])
            imageList = newImageList
        return imageList

    def getImage(self, cloudId, imageId):
        return self.getImages(cloudId, [imageId])[0]

    def getAllInstances(self, cloudId):
        return self.getInstances(cloudId, None)

    def getInstances(self, cloudId, instanceIds):
        globusInsts  = self.client[cloudId].listInstances()
        globusInstsDict = dict((x.getId(), x) for x in globusInsts)
        storeInstanceKeys = self.instanceStore.enumerate(cloudId)
        for storeKey in storeInstanceKeys:
            instanceId = os.path.basename(storeKey)
            reservationId = self.instanceStore.getId(storeKey)
            expiration = self.instanceStore.getExpiration(storeKey)
            if reservId is None and (expiration is None
                                     or time.time() > float(expiration)):
                # This instance exists only in the store, and expired
                self.instanceStore.delete(stKey)
                continue
            imageId = self.instanceStore.getImageId(stKey)

            # Did we find this instance in our store already?
            if reservId in reservIdHash:
                # If the previously found instance already has an image ID,
                # prefer it. Also, if neither this instance nor the other one
                # have an image ID, prefer the first (i.e. not this one)
                otherInstKey, otherInstImageId = reservIdHash[reservId]
                if otherInstImageId is not None or imageId is None:
                    instanceStore.delete(stKey)
                    continue

                # We prefer this instance over the one we previously found
                del reservIdHash[reservId]
                del tmpInstanceKeys[(otherInstKey, reservId)]

            if reservId is not None:
                reservIdHash[reservId] = (stKey, imageId)
            tmpInstanceKeys[(stKey, reservId)] = imageId

        # Done with the preference selection
        del reservIdHash

        gInsts = []

        # Walk through the list again
        for (stKey, reservId), imageId in tmpInstanceKeys.iteritems():
            if reservId is None:
                # The child process hasn't updated the reservation id yet (or
                # it died but the instance hasn't expired yet).
                # Synthesize a globuslib.Instance with not much info in it
                state = instanceStore.getState(stKey)
                inst = globuslib.Instance(_id = reservId, _state = state)
                gInsts.append((stKey, imageId, inst))
                continue

            reservId = int(reservId)
            if reservId not in globusInstsHash:
                # We no longer have this instance, get rid of it
                instanceStore.delete(stKey)
                continue
            # Instance exists both in the store and in globus
            inst = globusInstsHash.pop(reservId)
            gInsts.append((stKey, imageId, inst))
            # If a state file exists, get rid of it, we are getting the state
            # from globus
            instanceStore.setState(stKey, None)

        # For everything else, create an instance ID
        for reservId, inst in globusInstsHash.iteritems():
            nkey = instanceStore.newKey(realId = reservId)
            gInsts.append((nkey, None, inst))

        gInsts.sort(key = lambda x: x[1])

        instanceList = Instances()

        for stKey, imageId, instObj in gInsts:
            instId = str(os.path.basename(stKey))
            longInstId = os.path.join(prefix, instId)
            reservationId = instObj.getId()
            if reservationId is not None:
                reservationId = str(reservationId)
            inst = Instance(id = longInstId,
                imageId = imageId,
                instanceId = instId,
                reservationId = reservationId,
                dnsName = instObj.getName(),
                publicDnsName = instObj.getIp(), state = instObj.getState(),
                launchTime = instObj.getStartTime(),
                cloudName = cloudId,
                cloudType = 'vws',
                cloudAlias = self.cloudClient.getCloudAlias(),)

            nodes.append(inst)
        return nodes

    def _daemonize(self, function, *args, **kw):
        pid = os.fork()
        if pid:
            os.waitpid(pid, 0)
        try:
            try:
                pid = os.fork()
                if pid:
                    # The first child exits and is waited by the parent
                    os._exit(0)
                # Redirect stdin, stdout, stderr
                fd = os.open(os.devnull, os.O_RDWR)
                os.dup2(fd, 0)
                os.dup2(fd, 1)
                os.dup2(fd, 2)
                os.close(fd)
                # Create new process group
                os.setsid()

                os.chdir('/')
                function(*args, **kw)
            except Exception:
                os._exit(1)
        finally:
            os._exit(0)


    def _launchInstance(self, cloudId, imageId, instanceId, image,
                        duration, instanceType):
        try:
            self.instanceStore.setPid(instanceId)
            if not img.getIsDeployed():
                self.instanceStore.setState(instanceId, 'Downloading image')
                dlImagePath = self._downloadImage(img, imageExtraData)
                self.instanceStore.setState(instanceId, 'Preparing image')
                imgFile = self._prepareImage(dlImagePath)
                self.instanceStore.setState(instanceId, 'Publishing image')
                self._publishImage(imgFile)
            imageId = img.getImageId()

            def callback(realId):
                instanceStore.setId(instanceId, realId)
                # We no longer manage the state ourselves
                self.instanceStore.setState(instanceId, None)
            self.instanceStore.setState(instanceId, 'Launching')

            realId = self.cloudClient.launchInstances([imageId],
                duration = duration, callback = callback)

        finally:
            self.instanceStore.deletePid(instanceId)

    def _downloadImage(self, image, imageExtraData):
        imageId = image.getImageId()
        # Get rid of the trailing .gz
        assert(imageId.endswith('.gz'))
        imageSha1 = imageId[:-3]
        build = self._mintClient.getBuild(image.getBuildId())

        downloadUrl = imageExtraData['downloadUrl']
        # XXX temporary fix for a broken URL - misa 20080812
        downloadUrl = downloadUrl.replace('?id=', '?fileId=')

        # XXX follow redirects
        uobj = urllib.urlopen(downloadUrl)
        # Create temp file
        downloadFilePath = os.path.join(self.cloudClient._tmpDir,
            '%s.tgz' % imageSha1)
        util.copyfileobj(uobj, file(downloadFilePath, "w"))
        return downloadFilePath

    def _prepareImage(self, cloudId, downloadFilePath):
        retfile = self.client[cloudId]._repackageImage(downloadFilePath)
        os.unlink(downloadFilePath)
        return retfile

    def _publishImage(self, cloudId, fileName):
        self.client[cloudId].transferInstance(fileName)

    def _getImagesFromGrid(self, cloudId):
        imageIds = self.client[cloudId].listImages()
        imageList = Images()

        for imageId in imageIds:
            image = self._imageFactory(id = imageId,
                    imageId = imageId, isDeployed = True,
                    is_rBuilderImage = False,
                    shortName = os.path.basename(imageName),
                    longName = imageName,
                    cloudName = cloudId, cloudType = 'vws',
                    cloudAlias = self.client[cloudId].getCloudAlias())
            imageList.append(image)
        return imageList

    def _addMintDataToImageList(self, imageList):
        imageDataLookup = self.mintClient.getAllVwsBuilds()
        # Convert the images coming from rbuilder to .gz, to match what we're
        # storing in globus
        imageDataLookup = dict((x + '.gz', y)
            for x, y in imageDataLookup.iteritems())
        imageList = imageList[:]
        for image in imageList:
            imageId = image.getImageId()
            mintImageData = imageDataLookup.pop(imageId, {})
            image.setIs_rBuilderImage(bool(mintImageData))
            image.setIsDeployed(True)
            if not mintImageData:
                continue
            image.downloadUrl = mintImageData['downloadUrl']
            image.buildPageUrl = mintImageData['buildPageUrl']
            image.baseFileName = mintImageData['baseFileName']
            image.setBuildId(mintImageData['buildId'])

            for key, methodName in images.buildToNodeFieldMap.iteritems():
                getattr(image, methodName)(mintImageData[key])

            shortName = os.path.basename(mintImageData['baseFileName'])
            longName = "%s/%s" % (mintImageData['buildId'], shortName)
            image.setShortName(shortName)
            image.setLongName(longName)

        for imageId, mintImageData in imageDataLookup.iteritems():
            image = self._imageFactory(id = imageId,
                    imageId = imageId, isDeployed = False,
                    is_rBuilderImage = True,
                    buildId = mintImageData['buildId'],
                    longName = longName,
                    cloudName = cloudId, cloudType = 'vws',
                    cloudAlias = self.cloudClient.getCloudAlias())
            image.downloadUrl = mintImageData['downloadUrl']
            image.buildPageUrl = mintImageData['buildPageUrl']
            image.baseFileName = mintImageData['baseFileName']
            imageList.append(image)
        return imageList

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
        duration = node.getDuration()
        if duration is None:
            raise errors.ParameterError('duration was not specified')

        self.remoteIPAddress = clientSuppliedRemoteIP

        instanceType = node.getInstanceType()
        if instanceType is None:
            instanceType = 'vws.small'
        else:
            instanceType = instanceType.getId() or 'vws.small'
            instanceType = self._extractId(instanceType)
        self.instanceType = instanceType

    @staticmethod
    def _extractId(value):
        if value is None:
            return None
        return urllib.unquote(os.path.basename(value))




