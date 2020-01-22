import cerberus
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

class Base(object):
    def __init__(self, *args, **kwargs):
        print("Base __init__")

    @classmethod
    def _class_initialize(cls):
        print("Initializing {}".format(cls))


class _obj_validator(cerberus.Validator):
    def _validate_attrs(self, attrs, field, value):
        return True

class Crud(Base):
    _fields = {}
    _validator = None

    def __init__(self, **kwargs):
        super(Crud, self).__init__(**kwargs)
        print("Crud __init__")
        self.__field_values = {}
        for field in set(self._fields.keys()).intersection(set(kwargs.keys())):
            self.__field_values[field] = kwargs[field]


    def attr_getter(self, attr_name):
        return self.__field_values[attr_name]

    def attr_setter(self, attr_name, value):
        self.update(**{ attr_name: value })
        return self.attr_getter(attr_name)

    def update(self, **kwargs):
        update_fields = {}
        for field in set(self._fields.keys()).intersection(set(kwargs.keys())):
            if self.__field_values.get(field) is not kwargs[field]:
                update_fields[field] = kwargs[field]
        if update_fields:
            self._do_update_action(**update_fields)
        return self

    def _do_update_action(self, **kwargs):
        if not self._validator.validate(kwargs):
            raise Exception(self._validator.errors)
        self.__field_values.update(kwargs)

    @classmethod
    def _class_initialize(cls):
        super(Crud, cls)._class_initialize()
        cls._validator = _obj_validator(cls._fields)

        make_getter = lambda attr_name: lambda self: self.attr_getter(attr_name)
        make_setter = lambda attr_name: lambda self, value: self.attr_setter(attr_name, value)

        for attr_name, attr_detail in cls._fields.items():
            print("Setting {} to {}".format(attr_name, attr_detail))
            setattr(cls, attr_name, property(make_getter(attr_name), make_setter(attr_name)))


    @classmethod
    def create(cls, **kwargs):
        if not cls._validator.validate(kwargs):
            raise Exception(cls._validator.errors)

        return cls.instantiate(**kwargs)

    @classmethod
    def instantiate(cls, **kwargs):
        return cls(**kwargs)

    @classmethod
    def delete(cls, **kwargs):
        raise Exception("Abstract")

    @classmethod
    def search(cls,**kwargs):
        raise Exception("Abstract")


class Database(Crud):
    _engine = None
    _session = None

    __table__ = None
    __decl_base = declarative_base()
    __schema_class = None

    __type_map = {
        "string": String,
        "integer": Integer,
    }

    def __init__(self, **kwargs):
        super(Database, self).__init__(**kwargs)
        print("Database __init__")
        self.__data_obj = self.__schema_class(**kwargs)


    @classmethod
    def _class_initialize(cls):
        super(Database, cls)._class_initialize()
        schema_props = {
            field: Column(cls.__type_map[ cls._fields[field]["type"] ], **cls._fields[field]["attrs"]) for field in cls._fields
        }

        schema_props["__tablename__"] = cls.__table__

        cls.__schema_class = type(cls.__name__+"Schema", tuple([cls.__decl_base]), schema_props)
        cls.__decl_base.metadata.create_all(cls._engine)


    @classmethod
    def instantiate(cls, **kwargs):
        self = super(Database, cls).instantiate(**kwargs)
        sess = self._session()
        sess.add(self.__data_obj)
        sess.flush()
        return self

    def _do_update_action(self, **kwargs):
        super(Database, self)._do_update_action(**kwargs)
        sess = self._session.object_session(self.__data_obj)
        for field, value in kwargs.items():
            setattr(self.__data_obj, field, value)
        sess.flush()


class Sqlite(Database):
    _engine = create_engine('sqlite:///:memory:', echo=True)
    _session = sessionmaker(bind=_engine)

#TODO mark object dirty when fields change

#TODO sync changes when save called, or object goes out of scope
#     or just keep updating when the fields are changed

#TODO instead of keeping track of the fields as they change,
#     keep track of the state of the object when it first comes into being,
#     and then use that to see if an update is required when object is saved.
#     this should make a lot of the logic for setting up accessors and whatnot
#     quite a bit more simple