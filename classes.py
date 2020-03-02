import orm

class Identity(orm.Postgres):
    _table = "identity"
    _schema = {
        "identity": { "type": "string", "primary_key": True },
        "settings": { "type": "dict",   "default": {} },
    }

Identity._class_initialize()
