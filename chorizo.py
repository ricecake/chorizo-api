from api_tools import JsonApi
from twisted.internet import defer

import treq

json_api = JsonApi()


with json_api.subroute('/util') as util_api:
    @util_api.route('/ping',
        restricted=True,
    )
    def ping(request, **kwargs):
        return "pong"

json_api.run("localhost", 8089)