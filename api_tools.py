from functools import wraps
from klein import Klein
from twisted.internet import defer
import json
import cerberus
import treq
import time
import jwt
import re
from string import Template
from contextlib import contextmanager

class PkiCache(object):
    def __init__(self, ttl=3600):
        self.data = None
        self.map = {}
        self.ttl = ttl
        self.last_update = 0
        self.refreshing_deffered = None

    def refresh(self):
        if self.refreshing_deffered:
            return self.refreshing_deffered

        @defer.inlineCallbacks
        def finish(res, *args):
            try:
                self.data = yield treq.json_content(res)
                self.map.update({ x["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(x)) for x in self.data["keys"] if x["kid"] })
                self.last_update = time.time()
                self.refreshing_deffered = None
            except Exception as ex:
                print(ex)

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

    def key(self, keyName=None):
        return self.map.get(keyName)


class JsonApi(object):
    """
    Reusable class for composing a JSON API easily with minimal
    repeated code.
    """

    def __init__(self, app=None, cors=None):
        # TODO: Need to find a way to accept "Default" args for things like
        # restricted, and access levels...
        self.app = app if app else Klein()
        self.pki_cache = PkiCache()
        self.pki_cache.refresh()
        self.cors = cors

    def run(self, *args, **kwargs):
        return self.app.run(*args, **kwargs)

    def toJSON(self, data):
        """
        Serialize data to JSON
        """
        class ComplexEncoder(json.JSONEncoder):
            def default(self, obj):
                import orm
                if isinstance(obj, orm.Crud):
                    return obj.asDict()
                # Let the base class default method raise the TypeError
                return json.JSONEncoder.default(self, obj)

        return json.dumps(data, cls=ComplexEncoder)

    def defaultMiddleware(self, f):
        """
        Middleware to set application/json as default header for
        all responses.
        """
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[0]
            # if request.method is 'OPTIONS' and self.cors:
            #     status = 401
            #     request.getHeader()
            #     request.setHeader
            #     request.setResponseCode(status)
            #     return None

            request.setHeader('Content-Type', 'application/json')
            result = defer.maybeDeferred(f, *args, **kwargs)
            return result.addCallback(lambda res: self.toJSON(res))

        return deco

    def authenticate(self, f):
        """
        Middleware api-key authentication
        """
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[0]
            apiKey = None
            header = request.getHeader('Authorization')
            if header:
                result = re.search(r'^Bearer (\S+)$', header, re.IGNORECASE)
                if result:
                    apiKey = result.group(1)

            def auth_failure(cause):
                request.setResponseCode(401)
                return {
                    'scope': 'private',
                    'message': 'Sorry, valid credentials required to access content',
                    "cause": str(cause),
                }

            if not apiKey:
                return auth_failure("No auth")

            keyDef = self.pki_cache.get()

            def authedCall(keys):
                try:
                    kid = jwt.get_unverified_header(apiKey)['kid']
                    pubkey = self.pki_cache.key(kid)
                    kwargs["authed_user_data"] = jwt.decode(apiKey, pubkey, algorithm='RS256')
                except jwt.exceptions.InvalidTokenError as ex:
                    return auth_failure(ex)

                return defer.maybeDeferred(f, *args, **kwargs)

            keyDef.addCallback(authedCall)
            return keyDef


        return deco

    def authorize(self, f, required=[]):
        """
        Middleware api-key authentication
        """
        @wraps(f)
        def deco(*args, **kwargs):
            request = args[0]
            userData = kwargs["authed_user_data"]

            required = set(required) # This is where we need to loop through and expand template params using Template
            # for i in required:
            #    i = i.templplate($request.args)
            granted = set(userData.get("perm"))

            if not required <= granted:
                request.setResponseCode(401)
                return {
                    'scope': 'private',
                    'message': 'Insufficient permissions to execute method',
                    'lacking': list(required - granted),
                }

            return f(*args, **kwargs)

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
            acl = kwargs.pop('access_levels', [])
            validated = kwargs.pop('validation', False)

            # Note: these are run in reverse order that they are wrapped
            if restricted and acl:
                f = self.authorize(f, acl)

            if validated:
                f = self.validate(f, validation=validated)

            if restricted:
                f = self.authenticate(f)

            f = self.defaultMiddleware(f)
            self.app.route(url, *args, **kwargs)(f)
        return deco

    @contextmanager
    def subroute(self, prefix='/', options=None):
        preApp = self.app
        with self.app.subroute(prefix) as subApp:
            try:
                self.app = subApp
                yield self
            finally:
                self.app = preApp


    def autoCrud(self, namespace, *args, **kwargs):
        """
        Automatically generate basic crud routes for a class
        """
        pass