from django.core.files.storage import Storage


class FastDFSStoreage(Storage):
    def _open(self):
        pass

    def _save(self):
        pass

    def url(self, name):

        return 'http://127.0.0.1:8888/' + name