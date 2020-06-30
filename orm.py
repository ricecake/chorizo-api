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
                        'dict',
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
    def derivedClass(cls, **kwargs):
        return cls

    @classmethod
    def instantiate(cls, **kwargs):
        self = cls(**kwargs)
        return self

#### Create
    @classmethod
    def create(cls, **kwargs):
        # TODO: subclass projection logic goes here
        seen_classes = set()
        newCls = cls
        while newCls not in seen_classes:
            seen_classes.add(newCls)
            newCls = newCls.derivedClass(**kwargs)

        args = newCls._validator.normalized(kwargs)
        if not newCls._validator.validate(args):
            raise Exception(newCls._validator.errors)

        return newCls.instantiate(**args)

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

    def asDict(self):
        as_dict = {}
        for field in self._schema.keys():
            as_dict[field] = getattr(self, field, None)
        return as_dict


class Cursor(object):
    def __init__(self):
        pass
    def all(self):
        pass
    def first(self):
        pass
    def last(self):
        pass
    def next(self):
        pass
    def each(self):
        pass
    def count(self):
        pass


import psycopg2, psycopg2.extensions, psycopg2.extras, psycopg2.pool
import pypika
from contextlib import contextmanager

import config

class NestedTransactionConn(psycopg2.extras.RealDictConnection):
    def __init__(self, *args, **kwargs):
        self.__txn_depth = 0
        super(NestedTransactionConn, self).__init__(*args, **kwargs)
        self.autocommit = True

    def begin(self):
        if self.__txn_depth > 0:

        self.__txn_depth = self.__txn_depth + 1
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    @contextmanager
    def transaction(self):
        self.begin()
        try:
            yield self
        except Exception:
            self.rollback()
        else:
            self.commit()

class NestedTransactionCursor(psycopg2.extras.RealDictCursor):
    """
    This needs a reference to the owning connection.
    When a transaction method is called, it should update the transcount on the
    parent.  Need to make sure that the cursors all have the same
    transaction context, so that if we're nesting transactions, we're using the same cursor/connection/transaction
    """
    pass

psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)

conn_pool = psycopg2.pool.ThreadedConnectionPool(1, 20,
    user=config.file["db"]["username"].get(),
    password=config.file["db"]["password"].get(),
    host=config.file["db"]["host"].get(),
    database=config.file["db"]["database"].get(),
    connection_factory = NestedTransactionConn,
    cursor_factory = NestedTransactionCursor,
)



class Postgres(Crud):
    _table = None

    @classmethod
    def instantiate(cls, **kwargs):
        self = super(Postgres, cls).instantiate(**kwargs)

        keys = self._Crud__field_values.keys()
        table = pypika.Table(cls._table)
        query = pypika.PostgreSQLQuery.into(table).columns( *keys ).insert( *[pypika.Parameter("%({})s".format(k)) for k in keys ] ).returning('*')

        with conn_pool.getconn() as conn:
            print(conn.autocommit)
            with conn.cursor() as curr:
                curr.execute(query.get_sql(), self._Crud__field_values)
                data = curr.fetchone()

                for field in self._schema.keys():
                    self._Crud__field_values[field] = data.get(field, None)
                    setattr(self, field, data.get(field, None))

        return self

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
