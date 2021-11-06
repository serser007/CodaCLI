from coda import Coda


class CodaWorkspace:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)


class CodaPageRef:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.document_id = kwargs.get("document_id", None)

    def fetch(self):
        return self._coda.get_page(self.document_id, self.id)


class CodaPage:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.document_id = kwargs.get("document_id", None)
        self.children = list(map(
            lambda page: CodaPageRef(coda, document_id=self.document_id, **page),
            kwargs.get("children", [])
        ))

    def update(self, **kwargs):
        self._coda.update_page(self.document_id, self.id, **kwargs)


class CodaDocument:
    def __init__(self, coda: Coda, **kwargs):
        self._coda = coda
        self.name = kwargs.get("name", None)
        self.id = kwargs.get("id", None)
        self.workspace_id = kwargs.get("workspaceId", None)

    def pages(self):
        return self._coda.get_pages(self.id)
