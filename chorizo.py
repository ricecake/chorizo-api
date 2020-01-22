from klein import Klein
from api_tools import JsonApi
from twisted.internet import defer

import treq

json_api = JsonApi(app=Klein(), secret="cat")

@json_api.route('/', validation={ "test": { "type": "string" }}, restricted=True)
@defer.inlineCallbacks
def home(request):
    res = yield treq.get("https://login.devhost.dev/.well-known/openid-configuration")
    con = yield treq.text_content(res)
    defer.returnValue(con)

json_api.run("localhost", 8089)