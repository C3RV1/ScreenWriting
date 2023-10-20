import datetime

import typing
if typing.TYPE_CHECKING:
    from common.FountianParser import Block


class Document:
    def __init__(self, file_id):
        self.file_id = file_id
        self.blocks: typing.Optional[list[Block]] = None

    def open(self):
        pass

    def close(self):
        pass

    def save(self):
        pass

    @classmethod
    def from_dict(cls, d):
        return cls(d["file_id"])

    def to_dict(self):
        return {"file_id": self.file_id}


class TrashObject:
    def __init__(self, document, elimination_date):
        self.document: Document = document
        self.elimination_date: datetime.datetime = elimination_date

    @classmethod
    def from_dict(cls, d):
        return cls(Document.from_dict(d["document"]), d["expire_date"])

    def to_dict(self):
        return {"document": self.document.to_dict(), "expire_date": self.elimination_date}


class Folder:
    def __init__(self, folders, documents):
        self.folders: dict[str, Folder] = folders
        self.documents: dict[str, Document] = documents

    @classmethod
    def from_dict(cls, d):
        folders = {}
        documents = {}
        for name, folder_dict in d["folders"].items():
            folders[name] = Folder.from_dict(folder_dict)
        for name, document_dict in d["documents"].items():
            documents[name] = Document.from_dict(document_dict)
        return cls(folders, documents)

    def to_dict(self):
        return {
            "folders": {name: f.to_dict() for name, f in self.folders.items()},
            "documents": {name: d.to_dict() for name, d in self.documents.items()}
        }

    @classmethod
    def new(cls):
        return cls({}, {})


class Project:
    def __init__(self, name, filesystem: Folder, trash):
        self.name = name
        self.filesystem = filesystem
        self.trash: dict[str, TrashObject] = trash
        self.project_id = None

    def to_dict(self):
        return {
            "name": self.name,
            "filesystem": self.filesystem.to_dict(),
            "trash_objects": {name: to.to_dict() for name, to in self.trash.items()}
        }
