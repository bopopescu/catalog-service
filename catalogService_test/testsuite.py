#!/usr/bin/python
#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import os
import sys

from testrunner import suite, testhandler
class Suite(suite.TestSuite):
    # Boilerplate. We need these values saved in the caller module
    testsuite_module = sys.modules[__name__]
    suiteClass = testhandler.ConaryTestSuite
    topLevelStrip = 1

    execPathVarNames = [
        'CONARY_PATH',
        'CATALOG_SERVICE_PATH',
        'JOB_PATH',
        'MODELS_PATH',
        'RESTLIB_PATH',
        'SMARTFORM_PATH',
        'STORAGE_PATH',
        'XMLLIB_PATH',
    ]

    def setupPaths(self):
        testPath = os.getenv('TEST_PATH')
        testDir = os.path.basename(os.path.dirname(__file__))
        self.pathManager.addResourcePath('CATALOG_X509_CERTS',
            os.path.join(testPath, testDir, "x509_certs"))
        self.pathManager.addResourcePath('MOCKED_MODULES',
            os.path.join(testPath, testDir, 'mockedModules'))

        return testPath

    def setupSpecific(self):
        # ensure mocked modules come first absolutely
        self.pathManager.updatePaths(os.getenv('MOCKED_MODULES'))

    def getCoverageDirs(self, handler, environ):
        return [ self.pathManager.getCoveragePath('CATALOG_SERVICE_PATH') ]

    def getCoverageExclusions(self, handler, environ):
        return [ 'catalogService/libs/viclient_vendor',
                 'catalogService/libs/viclient' ]

_s = Suite()
setup = _s.setup
main = _s.main

if __name__ == '__main__':
    _s.run()
