from api_tools import JsonApi
from twisted.internet import defer

import treq

import classes

json_api = JsonApi()


with json_api.subroute('/util') as util_api:
    @util_api.route('/ping',
        restricted=True,
    )
    def util_ping(request, **kwargs):
        return "pong"

with json_api.subroute('/test') as test_api:
    import time
    @test_api.route('/ping',
        restricted=False,
    )
    def test_ping(request, **kwargs):
        return classes.Identity.create(identity="fooze: {}".format(time.time()))

json_api.run("localhost", 8089)
