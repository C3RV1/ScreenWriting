import datetime
import io
import os.path
import struct

import typing
if typing.TYPE_CHECKING:
    from common.FountianParser import Block
from bson import ObjectId


class Document:
    def __init__(self, file_id: str):
        self.file_id: str = file_id
        self.blocks: typing.Optional[list[Block]] = None

    @classmethod
    def from_fileid(cls, d):
        return cls(str(d))

    def to_fileid(self):
        return ObjectId(self.file_id)

    def to_bytes(self) -> bytes:
        if len(self.file_id) != 24:
            raise ValueError()
        return self.file_id.encode("ascii")

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        return cls(rdr.read(24).decode("ascii"))


class TrashObject:
    def __init__(self, document, elimination_date):
        self.document: Document = document
        self.elimination_date: datetime.datetime = elimination_date

    @classmethod
    def from_dict(cls, d):
        return cls(Document.from_fileid(d["document"]), d["expire_date"])

    def to_dict(self):
        return {"document": self.document.to_fileid(), "expire_date": self.elimination_date}

    def to_bytes(self) -> bytes:
        return self.document.to_bytes() + struct.pack("!Q", int(self.elimination_date.timestamp()))

    @classmethod
    def from_bytes(cls, rdr):
        document = Document.from_bytes(rdr)
        elimination_date = struct.unpack("!Q", rdr.read(8))[0]
        elimination_date = datetime.datetime.fromtimestamp(elimination_date)
        return cls(document, elimination_date)


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
            documents[name] = Document.from_fileid(document_dict)
        return cls(folders, documents)

    def to_dict(self):
        return {
            "folders": {name: f.to_dict() for name, f in self.folders.items()},
            "documents": {name: d.to_fileid() for name, d in self.documents.items()}
        }

    @classmethod
    def new(cls):
        return cls({}, {})

    def to_bytes(self) -> bytes:
        msg = struct.pack("!BB", len(self.folders), len(self.documents))
        for folder_name, folder in self.folders.items():
            folder_name_encoded = folder_name.encode("utf-8")
            msg += struct.pack("!B", len(folder_name_encoded)) + folder_name_encoded + folder.to_bytes()
        for document_name, document in self.documents.items():
            document_name_encoded = document_name.encode("utf-8")
            msg += struct.pack("!B", len(document_name_encoded)) + document_name_encoded + document.to_bytes()
        return msg

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        folder_count, document_count = struct.unpack("!BB", rdr.read(2))
        folders = {}
        documents = {}
        for i in range(folder_count):
            folder_name_len = struct.unpack("!B", rdr.read(1))[0]
            folder_name = rdr.read(folder_name_len).decode("utf-8")
            folders[folder_name] = Folder.from_bytes(rdr)
        for i in range(document_count):
            document_name_len = struct.unpack("!B", rdr.read(1))[0]
            document_name = rdr.read(document_name_len).decode("utf-8")
            documents[document_name] = Document.from_bytes(rdr)
        return cls(folders, documents)


class Project:
    def __init__(self, name, filesystem: Folder, trash):
        self.name: str = name
        self.filesystem: Folder = filesystem
        self.trash: dict[str, TrashObject] = trash
        self.project_id: typing.Optional[str] = None

    def create_folder(self, path):
        path_split = [path]
        while path_split[0] != "":
            v = path_split.pop(0)
            path_split = list(os.path.split(v)).extend(path_split)
        path_split = path_split[1:]

        current_folder = self.filesystem
        while len(path_split) != 1:
            v = path_split.pop(0)
            if v not in current_folder.folders:
                return None, "Parent folder not found."
            current_folder = current_folder.folders[v]
        folder_name = path_split.pop(0)
        if folder_name in current_folder:
            return None, "Folder already exists."
        current_folder.folders[folder_name] = Folder.new()
        return current_folder.folders[folder_name], None

    def to_dict(self):
        return {
            "name": self.name,
            "filesystem": self.filesystem.to_dict(),
            "trash_objects": {name: to.to_dict() for name, to in self.trash.items()}
        }

    def to_bytes(self):
        name_encoded = self.name.encode("utf-8")
        trash_count = len(self.trash)
        msg = self.project_id.encode("ascii") + struct.pack("!BH", len(name_encoded), trash_count)
        msg += name_encoded
        msg += self.filesystem.to_bytes()
        for name, trash_obj in self.trash.items():
            name_encoded = name.encode("utf-8")
            msg += struct.pack("!B", len(name_encoded))
            msg += trash_obj.to_bytes()
        return msg

    @classmethod
    def from_bytes(cls, rdr: io.BytesIO):
        project_id = rdr.read(24).decode("ascii")
        name_len, trash_len = struct.unpack("!BH", rdr.read(3))
        project_name = rdr.read(name_len).decode("utf-8")
        filesystem = Folder.from_bytes(rdr)
        trash = {}
        for i in range(trash_len):
            name_len = struct.unpack("!B", rdr.read(1))[0]
            name = rdr.read(name_len).decode("utf-8")
            trash[name] = TrashObject.from_bytes(rdr)
        proj = Project(project_name, filesystem, trash)
        proj.project_id = project_id
        return proj
