import requests
import jwt
import time
class Cache(object):
    def __init__(self, ttl=3600):
        self.data = None
        self.ttl = ttl
        self.last_update = 0

    def refresh(self):
        try:
            self.data = self.do_refresh()
            self.last_update = time.time()
        except Exception as ex:
            print(ex)

    def do_refresh(self):
        pass

    def get(self):
        if not self.data:
            self.refresh()
        elif time.time() - self.last_update > self.ttl:
            self.refresh()

        return self.data

#TODO: Need a url builder to build urls from hosts
class PkiCache(Cache):
    def __init__(self):
        self.map = {}
        return super(PkiCache, self).__init__()

    def do_refresh(self):
        r = requests.get('https://login.devhost.dev/publickeys')

        data = r.json()
        self.map.update({ x["kid"]: jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(x)) for x in data["keys"] if x["kid"] })
        return data

    def key(self, keyName=None):
        self.get()
        return self.map.get(keyName)

class RevCache(Cache):
    def __init__(self):
        return super(RevCache, self).__init__()

    def do_refresh(self):
        r = requests.get('https://login.devhost.dev/revocation')

        data = r.json()
        return data




class JsonApiError(Exception):
    def __init__(self, code=500, scope='private', message='Something went wrong', cause='Internal Error'):
        self.code  = code
        self.scope = scope
        self.message = message
        self.cause = cause

    def asDict(self):
        return {
            'code': self.code,
            'scope': self.scope,
            'message': self.message,
            "cause": str(self.cause),
        }

class JsonApiAuthError(JsonApiError):
    def __init__(self, **kwargs):
        kwargs['code'] = 401
        kwargs['message'] = 'Sorry, valid credentials required to access content'
        return super(JsonApiAuthError, self).__init__(**kwargs)

import re
import json
import cerberus
from flask import Flask, escape, request, Response
from contextlib import contextmanager
from functools import wraps
class JsonApi(Flask):
    def __init__(self, *args, **kwargs):
        self.prefix = None
        self.pki_cache = PkiCache()
        self.pki_cache.refresh()
        self.rev_cache = RevCache()
        self.rev_cache.refresh()
        return super(JsonApi, self).__init__(*args, **kwargs)

    @staticmethod
    def join_url_path(*parts):
        return '/'+ '/'.join([ part.strip('/') for part in parts if part ])

    @staticmethod
    def toJSON(data):
        """
        Serialize data to JSON
        """
        class ComplexEncoder(json.JSONEncoder):
            def default(self, obj):
                if callable(getattr(obj, 'asDict', None)):
                    return obj.asDict()
                # Let the base class default method raise the TypeError
                return json.JSONEncoder.default(self, obj)

        return json.dumps(data, cls=ComplexEncoder)

    def route(self, path, *args, **kwargs):
        acl = kwargs.pop('access_levels', [])
        restricted = kwargs.pop('restricted', False)
        validated = kwargs.pop('validation', False)

        if self.prefix:
            path = self.join_url_path(self.prefix, path)

        def deco(f):
            # Note: these are run in reverse order that they are wrapped
            if restricted and acl:
                f = self.authorize(f, acl)

            if validated:
                f = self.validate(f, validation=validated)

            if restricted:
                f = self.authenticate(f)

            f = self.defaultMiddleware(f)

            return super(JsonApi, self).route(path, *args, **kwargs)(f)

        return deco

    @contextmanager
    def subroute(self, prefix='/', options=None):
        old_prefix = self.prefix
        try:
            self.prefix = self.join_url_path(self.prefix, prefix)
            yield self
        finally:
            self.prefix = old_prefix

    def defaultMiddleware(self, f):
        """
        Middleware to set application/json as default header for
        all responses.
        """
        @wraps(f)
        def deco(*args, **kwargs):
            # if request.method is 'OPTIONS' and self.cors:
            #     status = 401
            #     request.getHeader()
            #     request.setHeader
            #     request.setResponseCode(status)
            #     return None

            resp = None
            try:
                result = f(*args, **kwargs)
                resp = Response(self.toJSON(result))
            except JsonApiError as err:
                resp = Response(self.toJSON(err), err.code)

            resp.headers['Content-Type'] = 'application/json'

            return resp

        return deco

    def authenticate(self, f):
        """
        Middleware api-key authentication
        """
        @wraps(f)
        def deco(*args, **kwargs):
            apiKey = None
            header = request.headers.get('Authorization')
            if header:
                result = re.search(r'^Bearer (\S+)$', header, re.IGNORECASE)
                if result:
                    apiKey = result.group(1)

            if not apiKey:
                raise JsonApiAuthError(cause="No auth")

            try:
                kid = jwt.get_unverified_header(apiKey)['kid']
                pubkey = self.pki_cache.key(kid)
                kwargs["authed_user_data"] = jwt.decode(apiKey, pubkey, algorithm='RS256')
            except jwt.exceptions.InvalidTokenError as ex:
                raise JsonApiAuthError(cause=ex)

            return f(*args, **kwargs)

        return deco

    def validate(self, f, validation=None):
        """
        Middleware for basic validation of input
        """
        v = cerberus.Validator(validation)

        @wraps(f)
        def deco(*args, **kwargs):
            content = request.get_json(force=True, silent=True)
            if not content:
                raise JsonApiError(
                    code=400,
                    message='Input Required',
                    cause='No Input',
                )

            if not v.validate(content):
                raise JsonApiError(
                    code=422,
                    message='Invalid input',
                    cause=v.errors,
                )
            return f(*args, **kwargs)

        return deco

    def authorize(self, f, required=[]):
        """
        Middleware api-key authentication
        """
        @wraps(f)
        def deco(*args, **kwargs):
            userData = kwargs["authed_user_data"]

            required = set(required) # This is where we need to loop through and expand template params using Template
            # for i in required:
            #    i = i.templplate($request.args)
            granted = set(userData.get("perm"))

            if not required <= granted:
                raise JsonApiError(
                    code=401,
                    message='Insufficient permissions to execute method',
                    cause=list(required - granted),
                )

            return f(*args, **kwargs)

        return deco

    def autoCrud(self, namespace, *args, **kwargs):
        """
        Automatically generate basic crud routes for a class
        """
        pass
