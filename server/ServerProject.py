import threading

from common.Project import Project, Folder, TrashObject, Document
from server.RealTimeDocument import RealTimeDocument
import typing
if typing.TYPE_CHECKING:
    from server.ClientHandler import ClientHandler
from server.Config import ServerConfig
from pymongo import database
import bson
import datetime
import os


class ServerProject(Project):
    def __init__(self, name, filesystem: Folder, trash):
        super().__init__(name, filesystem, trash)
        self.opened_users: list['ClientHandler'] = []
        self.current_realtime_documents: list[RealTimeDocument] = []
        self.project_lock = threading.RLock()

    def update_trash(self):
        documents_to_eliminate = []
        for name, trash_document in self.trash.items():
            max_delta = datetime.timedelta(days=ServerConfig.MAX_TRASH_CAN_DAYS)
            if trash_document.elimination_date - datetime.datetime.now(datetime.timezone.utc) > max_delta:
                documents_to_eliminate.append(name)

        for document in documents_to_eliminate:
            trash_obj = self.trash.pop(document)
            self.destroy_document(trash_obj.document)

    @staticmethod
    def destroy_document(document: Document):
        path = os.path.join("documents", document.file_id + ".fountain")
        if not os.path.isfile(path):
            return
        os.remove(path)
        document.file_id = None

    def save_to_database(self, db: database.Database):
        project_collection = db["projects"]
        update_result = project_collection.update_one(
            {
                "name": self.name
            },
            {
                "$set": {
                    "filesystem": self.filesystem.to_dict(),
                    "trash": {name: to.to_dict() for name, to in self.trash.items()}
                }
            },
            upsert=(self.project_id is None)
        )
        # If the project_id is None, then it did not previously exist.
        if self.project_id is None:
            self.project_id = str(update_result.upserted_id)

    def save_filesystem(self, db: database.Database):
        if self.project_id is None:
            return
        project_collection = db["projects"]
        project_collection.update_one(
            {
                "_id": bson.ObjectId(self.project_id)
            },
            {
                "$set": {
                    "filesystem": self.filesystem.to_dict(),
                }
            }
        )

    def save_trash(self, db: database.Database):
        if self.project_id is None:
            return
        project_collection = db["projects"]
        project_collection.update_one(
            {
                "_id": bson.ObjectId(self.project_id)
            },
            {
                "$set": {
                    "trash": {name: to.to_dict() for name, to in self.trash.items()}
                }
            }
        )

    def remove_from_database(self, db: database.Database):
        print(f"Deleting project {self.project_id}")
        if self.project_id is None:
            return
        project_collection = db["projects"]
        project_collection.delete_one({
            "_id": bson.ObjectId(self.project_id)
        })

        def walk_destroy_folder(f: Folder):
            for doc in f.documents.values():
                self.destroy_document(doc)
            for folder in f.folders.values():
                walk_destroy_folder(folder)

        walk_destroy_folder(self.filesystem)

        for to in self.trash.values():
            self.destroy_document(to.document)

        for user in self.opened_users:
            user.open_project = None
            user.open_real_time_documents = {}
        self.project_id = None

    @staticmethod
    def exists_project(db: database.Database, project_name: str):
        project_collection = db["projects"]
        return project_collection.find_one({"name": project_name}) is not None

    @staticmethod
    def exists_project_by_id(db: database.Database, project_id: str):
        project_collection = db["projects"]
        return project_collection.find_one({"_id": bson.ObjectId(project_id)}) is not None

    @classmethod
    def load_by_name(cls, db: database.Database, project_name: str):
        project_collection = db["projects"]
        project_entry = project_collection.find_one({"name": project_name})
        if project_entry is None:
            return None
        project = cls(project_name, Folder.from_dict(project_entry["filesystem"]),
                      {name: TrashObject.from_dict(to) for name, to in project_entry["trash"].items()})
        project.project_id = str(project_entry["_id"])
        return project

    @classmethod
    def load_from_id(cls, db: database.Database, project_id: str):
        project_collection = db["projects"]
        project_entry = project_collection.find_one({"_id": bson.ObjectId(project_id)})
        if project_entry is None:
            return None
        project = cls(project_entry["name"], Folder.from_dict(project_entry["filesystem"]),
                      {name: TrashObject.from_dict(to) for name, to in project_entry["trash"].items()})
        project.project_id = project_id
        return project
