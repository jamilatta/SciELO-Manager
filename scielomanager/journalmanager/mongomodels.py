# coding:utf8
from urlparse import urlparse

from django.conf import settings
import pymongo


MONGO_URI = getattr(settings, 'MONGO_URI',
    'mongodb://localhost:27017/journalmanager')


class DbOperationsError(Exception):
    """Represents all possible exceptions while interacting with
    MongoDB.
    """


class MongoConnector(object):
    """
    Connects to MongoDB and makes self.db and self.col
    available to the instance.
    """

    def __init__(self, mongodb_driver=pymongo,
                       mongo_uri=MONGO_URI,
                       mongo_collection=None):
        db_url = urlparse(mongo_uri)
        self._conn = mongodb_driver.Connection(host=db_url.hostname,
                                               port=db_url.port)
        self.db = self._conn[db_url.path[1:]]
        if db_url.username and db_url.password:
            self.db.authenticate(db_url.username, db_url.password)

        self.col = self.db[mongo_collection] if mongo_collection else None

        #  ensure indexes if they exist
        if hasattr(self, '_ensure_indexes'):
            self._ensure_indexes()


class MongoManager(MongoConnector):
    """
    Wraps a subset of pymongo.collection.Collection methods, in order
    to act as a manager for mongodb documents. The collection must be
    set, in instantiation, using the ``mongo_collection`` arg.

    The exposed methods must be in the ``exposed_api_methods`` list.

    See the pymongo docs for more information about using the exposed
    methods:
    http://api.mongodb.org/python/current/api/pymongo/collection.html
    """
    exposed_api_methods = ['find', 'find_one']

    def __init__(self, doc, **kwargs):
        self._doc = doc

        # introspect the ``self._doc`` class to discover the collection name
        if 'mongo_collection' not in kwargs:
            kwargs['mongo_collection'] = self._doc._collection_name_

        super(MongoManager, self).__init__(**kwargs)

    def __getattr__(self, name):

        if name in self.exposed_api_methods:
            if not self.col:
                raise ValueError(
                    'method %s needs a collection to be defined' % name)

            if hasattr(self.col, name):
                return getattr(self.col, name)
            else:
                raise AttributeError()
        else:
            # django makes mystical things on attr retrieval
            super(MongoManager, self).__getattr__(name)


class ManagerFactory(object):
    def __get__(self, instance, cls):
        if not hasattr(cls, '_objects'):
            setattr(cls, '_objects', MongoManager(cls))

        return cls._objects


class Article(MongoConnector):
    _collection_name_ = 'articles'
    objects = ManagerFactory()

    init_params = ['mongodb_driver', 'mongo_uri', 'mongo_collection']

    def __init__(self, **kwargs):
        # cleaning up init args
        init_args = {}
        for param in self.init_params:
            if param in kwargs:
                init_args[param] = kwargs.pop(param)

        if 'mongo_collection' not in init_args:
            init_args['mongo_collection'] = 'articles'

        super(Article, self).__init__(**init_args)

        self._data = kwargs

    def _ensure_indexes(self):
        """
        Registers all the MongoDB indexes needed by Article instances
        """
        self.col.ensure_index('issue_ref')

    def __setattr__(self, name, value):
        # only some attributes are allowed to be set in the instance
        if name in ['_conn', 'db', 'col', '_data']:
            super(Article, self).__setattr__(name, value)
        else:
            _data = self.__dict__.setdefault('_data', {})
            _data[name] = value

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        else:
            raise AttributeError(
                "'%s' object has no attribute '%s'" % (self.__class__, name)
            )

    def save(self):
        try:
            return self.col.save(self._data, safe=True)
        except pymongo.errors.PyMongoError, exc:
            raise DbOperationsError(exc)

    @property
    def original_title(self):
        try:
            return self._data['title-group'][self._data['default-language']]
        except KeyError:
            return u''
