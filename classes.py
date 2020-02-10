import orm

class SubclassA(orm.Crud):
    __table__ = "foo"
    _schema = {
        "a": { "type": "integer", "primary_key": True },
        "b": { "type": "integer", },
        "c": { "type": "integer", },
        "d": { "type": "integer", "default": 99 },
    }

SubclassA._class_initialize()
