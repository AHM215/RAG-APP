# from .BaseDataModel import BaseDataModel
# from .minirag.schemes import Project
# from .enums.DataBaseEnum import DatabaseEnum

# class ProjectModel(BaseDataModel):
#     def __init__(self, db_client):
#         super().__init__(db_client)
#         self.collection = self.db_client[DatabaseEnum.COLLECTION_PROJECT_NAME.value]

#     async def init_collection(self):
#         all_collections = await self.db_client.list_collection_names()
#         if DatabaseEnum.COLLECTION_PROJECT_NAME.value not in all_collections:
#             await self.db_client.create_collection(DatabaseEnum.COLLECTION_PROJECT_NAME.value)
#             # Create indexes for the collection
#             indexes = Project.get_indexes()
#             for index in indexes:
#                 await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])
    
#     @classmethod
#     async def create_instance(cls, db_client):
#         instance = cls(db_client)
#         await instance.init_collection()
#         return instance

#     # Add methods for project management here, e.g., create_project, get_project_or_create_one, get_all_projects, etc.

#     async def create_project(self, project: Project):
#         project_dict = project.dict(by_alias=True, exclude_unset=True)
#         result = await self.collection.insert_one(project_dict)
#         return result.inserted_id
    
#     async def get_project_or_create_one(self, project_id: str):
#         project = await self.collection.find_one({"project_id": project_id})
        
#         if project:
#             return Project(**project)
        
#         new_project = Project(project_id=project_id)
#         _ = await self.create_project(new_project)
#         return new_project
    
#     ## build with pagination with total no of documents.
#     async def get_all_projects(self, page: int = 1, page_size: int = 10):
#         total_documents = await self.collection.count_documents({})

#         total_pages = (total_documents + page_size - 1) // page_size

#         skip = (page - 1) * page_size

#         cursor = self.collection.find().skip(skip).limit(page_size)
#         projects = []
#         async for document in cursor:
#             projects.append(Project(**document))
#         return projects, total_pages


from .BaseDataModel import BaseDataModel
from .minirag import Project
from .enums.DataBaseEnum import DatabaseEnum
from sqlalchemy.future import select
from sqlalchemy import func

class ProjectModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        return instance

    async def create_project(self, project: Project):
        async with self.db_client() as session:
            async with session.begin():
                session.add(project)
            await session.commit()
            await session.refresh(project)
        
        return project

    async def get_project_or_create_one(self, project_id: int):
        async with self.db_client() as session:
            async with session.begin():
                query = select(Project).where(Project.project_id == project_id)
                result = await session.execute(query)
                project = result.scalar_one_or_none()
                if project is None:
                    project_rec = Project(
                        project_id = project_id
                    )

                    project = await self.create_project(project=project_rec)
                    return project
                else:
                    return project

    async def get_all_projects(self, page: int=1, page_size: int=10):

        async with self.db_client() as session:
            async with session.begin():

                total_documents = await session.execute(select(
                    func.count( Project.project_id )
                ))

                total_documents = total_documents.scalar_one()

                total_pages = total_documents // page_size
                if total_documents % page_size > 0:
                    total_pages += 1

                query = select(Project).offset((page - 1) * page_size ).limit(page_size)
                projects = await session.execute(query).scalars().all()

                return projects, total_pages