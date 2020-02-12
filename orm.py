import cerberus

class Base(object):
    def __init__(self, *args, **kwargs):
        print("Base __init__")

    @classmethod
    def _class_initialize(cls):
        print("Initializing {}".format(cls))


def validator_from_schema(schema):
    base_validator = {}
    for key, value in schema.items():
        base_validator[key] = { "type": value["type"] }
        default = value.get("default")
        if default is not None:
            base_validator[key]["default"] = default

    return base_validator

schema_validator = cerberus.Validator({
    "schema": {
        "type": "dict",
        "keysrules":{
            "type": "string",
            "regex": '^[0-9a-zA-Z_]+$'
        },
        "valuesrules": {
            "type": "dict",
            "schema": {
                "type": {
                    "required": True,
                    "allowed": [
                        'string',
                        'integer',
                        'float',
                        'binary',
                        'datetime',
                        'date',
                        'boolean',
                    ],
                },
                "primary_key": {
                    "type": "boolean"
                },
                "default": {
                    "required": False,
                },
            }
        },
    },
})

class Crud(Base):
    _schema = {}
    _validator = None

### Class Methods
    @classmethod
    def _class_initialize(cls):
        schema_validator.validate(cls._schema)
        super(Crud, cls)._class_initialize()
        validator = validator_from_schema(cls._schema)
        cls._validator = cerberus.Validator(validator)

    @classmethod
    def instantiate(cls, **kwargs):
        return cls(**kwargs)

#### Create
    @classmethod
    def create(cls, **kwargs):
        args = cls._validator.normalized(kwargs)
        if not cls._validator.validate(args):
            raise Exception(cls._validator.errors)

        return cls.instantiate(**args)

#### Retrieve
    @classmethod
    def search(cls,**kwargs):
        raise Exception("Abstract")

    @classmethod
    def find(cls, **kwargs):
        raise Exception("Abstract")


#### Update
    @classmethod
    def updateClass(cls, **kwargs):
        raise Exception("Abstract")

#### Delete
    @classmethod
    def deleteClass(cls, **kwargs):
        raise Exception("Abstract")

### Instance methods

    def __init__(self, **kwargs):
        super(Crud, self).__init__(**kwargs)
        print("Crud __init__")
        self.__field_values = {}

        all_keys = set(self._schema.keys())
        passed_keys = set(kwargs.keys())

        for field in all_keys.intersection(passed_keys):
            if getattr(self, field, None) is None:
                fieldValue = kwargs.get(field, self._schema[field].get("default"))
                setattr(self, field, fieldValue)
                self.__field_values[field] = fieldValue

        for field in all_keys.difference(passed_keys):
            if getattr(self, field, None) is None:
                fieldValue = self._schema[field].get("default")
                setattr(self, field, fieldValue)
                self.__field_values[field] = fieldValue


    def update(self, **kwargs):
        update_fields = {}
        for field in set(self._schema.keys()).intersection(set(kwargs.keys())):
            if getattr(self, field, None) is not kwargs[field]:
                update_fields[field] = kwargs[field]
        if update_fields:
            self._pre_update(**update_fields)
            self._do_update_action(**update_fields)
            self._post_update(**update_fields)
        return self


    def _pre_update(self, **kwargs):
        result_value = self.__field_values.copy()
        result_value.update(kwargs)
        if not self._validator.validate(result_value):
            raise Exception(self._validator.errors)

    def _do_update_action(self, **kwargs):
        for field, value in kwargs.items():
            setattr(self, field, value)
        self.sync()

    def _post_update(self, **kwargs):
        pass

    def changed(self):
        current = {}
        for field in self._schema.keys():
            current[field] = getattr(self, field, None)

        return current != self.__field_values

    def sync(self):
        for field in self._schema.keys():
            self.__field_values[field] = getattr(self, field, None)

#TODO mark object dirty when fields change

#TODO sync changes when save called, or object goes out of scope
#     or just keep updating when the fields are changed

#TODO instead of keeping track of the fields as they change,
#     keep track of the state of the object when it first comes into being,
#     and then use that to see if an update is required when object is saved.
#     this should make a lot of the logic for setting up accessors and whatnot
#     quite a bit more simple

#TODO For the crud part, make a context manager that returns the pypika table object,
#     so that criteria can be set on it, and then when the context closes, the query executes
#     with Obj.searchWith as filter:
#         filter.a = 4
#         filter.baz = 6