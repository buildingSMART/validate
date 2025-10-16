from rest_framework import versioning

class OptionalURLPathVersioning(versioning.URLPathVersioning):
    default_version = 1
    version_param = 'version'
    allowed_versions = ['1', '1.0']

VERSION = r'v(?P<version>\d+)/'
OPTIONAL_VERSION = r'(v(?P<version>(\d+(\.\d+)?(\.\d+)?))/)?'