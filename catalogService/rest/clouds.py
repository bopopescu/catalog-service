import urllib

from restlib import controller

from base import BaseController

from catalogService import clouds
from catalogService import environment
from catalogService import images
from catalogService import instances
from catalogService import keypairs
from catalogService import nodeFactory
from catalogService import securityGroups

from catalogService.rest.response import XmlResponse


class BaseCloudController(controller.RestController):
    def __init__(self, parent, path, driver, cfg):
        self.cfg = cfg
        self.driver = driver
        controller.RestController.__init__(self, parent, path, [driver, cfg])

class ImagesController(BaseCloudController):
    modelName = 'imageId'

    def index(self, request, cloudName):
        imgNodes = self.driver(request, cloudName).getAllImages()
        return XmlResponse(imgNodes)

class InstancesController(BaseCloudController):
    modelName = 'instanceId'
    def index(self, request, cloudName):
        insts = self.driver(request, cloudName).getAllInstances()
        return XmlResponse(insts)

    def create(self, request, cloudName):
        "launch a new instance"
        insts = self.driver(request, cloudName).launchInstance(request.read(),
                                                               request.host)
        return XmlResponse(insts)

    def destroy(self, request, cloudName, instanceId):
        insts = self.driver(request, cloudName).terminateInstance(instanceId)
        return XmlResponse(insts)

class InstanceTypesController(BaseCloudController):
    modelName = 'instanceTypeId'

    def index(self, request, cloudName):
        return XmlResponse(self.driver(request, cloudName).getInstanceTypes())

class UserEnvironmentController(BaseCloudController):
    def index(self, request, cloudName, userName):
        return XmlResponse(self.driver(request, cloudName).getEnvironment())


class UsersController(BaseCloudController):
    modelName = 'userName'

    urls = dict(environment = UserEnvironmentController)

class CloudTypeModelController(BaseCloudController):

    modelName = 'cloudName'

    urls = dict(images = ImagesController,
                instances = InstancesController,
                users = UsersController,
                instanceTypes = InstanceTypesController)

    def splitId(self, url):
        cloudName, rest = BaseCloudController.splitId(self, url)
        cloudName = urllib.unquote(cloudName)
        # note - may want to do further validation at the time of
        # passing the cloud name into the function...
        if not self.driver.isValidCloudName(cloudName):
            raise UnsupportedCloudId(cloudName)
        return cloudName, rest

    def index(self, request):
        'iterate available clouds'
        return XmlResponse(self.driver(request).listClouds())

SUPPORTED_MODULES = ['ec2', 'vws']

class AllCloudController(BaseController):

    def index(self, request):
        cloudNodes = clouds.BaseClouds()
        for cloudType, cloudController in sorted(self.urls.items()):
            cloudNodes.extend(cloudController.driver(request).listClouds())
        return XmlResponse(cloudNodes)

    def loadCloudTypes(self):
        drivers = []
        self.urls = {}
        moduleDir =  __name__.rsplit('.', 1)[0] + '.drivers'
        for driverName in SUPPORTED_MODULES:
            driverClass = __import__('%s.%s' % (moduleDir, driverName),
                                      {}, {}, ['drivers']).driver
            driver = driverClass(self.cfg, driverName)
            controller =  CloudTypeModelController(self, driverName,
                                                   driver, self.cfg)
            self.urls[driverName] = controller
