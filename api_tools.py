from functools import wraps
from klein import Klein
from twisted.internet import defer
import json
import cerberus
import treq
import time


class PkiCache(object):
    def __init__(self, ttl=3600):
        self.data = None
        self.ttl = ttl
        self.last_update = 0
        self.refreshing_deffered = None

    def refresh(self):
        if self.refreshing_deffered:
            return self.refreshing_deffered

        @defer.inlineCallbacks
        def finish(res, *args):
            self.data = yield treq.json_content(res)
            self.last_update = time.time()
            self.refreshing_deffered = None

        reqCb = treq.get('https://login.devhost.dev/publickeys')
        reqCb.addCallback(finish, lambda err: print(err))
        self.refreshing_deffered = reqCb
        return reqCb

    @defer.inlineCallbacks
    def get(self):
        result = None
        if self.data:
            result = self.data
        else:
            yield self.refresh()
            result = self.data

        if time.time() - self.last_update > self.ttl:
            self.refresh()

        defer.returnValue(result)


class JsonApi(object):
    """
    Reusable class for composing a JSON API easily with minimal
    repeated code.
    """

    def __init__(self, app=None):
        self.app = app if app else Klein()
        self.pki_cache = PkiCache()
        self.pki_cache.refresh()

    def run(self, *args, **kwargs):
        return self.app.run(*args, **kwargs)

    def toJSON(self, data):
        """
        Serialize data to JSON
        """
        return json.dumps(data)

    def defaultMiddleware(self, f):
        """
        Middleware to set application/json as default header for
        all responses.
        """
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[0]
            request.setHeader('Content-Type', 'application/json')
            result = defer.maybeDeferred(f, *args, **kwargs)
            return result.addCallback(lambda res: self.toJSON(res))

        return deco

    def authenticate(self, f, authData=False):
        """
        Middleware api-key authentication
        """
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[0]
            apiKey = request.getHeader('Authorization')
            if apiKey:
                keyDef = self.pki_cache.get()

                def authedCall(keys):
                    if not apiKey or apiKey != self.secret:
                        request.setResponseCode(401)
                        return {
                            'scope': 'private',
                            'message': 'Sorry, valid credentials required to access content'
                        }
                    return defer.maybeDeferred(f, *args, **kwargs)

                keyDef.addCallback(authedCall)
                return keyDef
            else:
                request.setResponseCode(401)
                return {
                    'scope': 'private',
                    'message': 'Sorry, valid credentials required to access content'
                }


        return deco

    def validate(self, f, validation=None):
        """
        Middleware for basic validation of input
        """
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[0]
            content = json.loads(request.content.read())
            request.args.update(content)
            v = cerberus.Validator(validation)
            if not v.validate(request.args):
                request.setResponseCode(422)
                return {
                    'scope': 'private',
                    'message': 'Invalid input',
                    'errors': v.errors,
                }
            return f(*args, **kwargs)

        return deco

    def route(self, url, *args, **kwargs):
        """
        Extend the route functionality
        """
        def deco(f):
            restricted = kwargs.pop('restricted', False)
            validated = kwargs.pop('validation', False)

            if validated:
                f = self.validate(f, validation=validated)

            if restricted:
                f = self.authenticate(f, restricted)

            f = self.defaultMiddleware(f)
            self.app.route(url, *args, **kwargs)(f)
        return deco

    def autoCrud(self, namespace, *args, **kwargs):
        """
        Automatically generate basic crud routes for a class
        """
        pass