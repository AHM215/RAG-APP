from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from .enums.DataBaseEnum import DatabaseEnum

class ProjectModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.COLLECTION_PROJECT_NAME.value]

    # Add methods for project management here, e.g., create_project, get_project_or_create_one, get_all_projects, etc.

    async def create_project(self, project: Project):
        project_dict = project.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(project_dict)
        return str(result.inserted_id)
    
    async def get_project_or_create_one(self, project_id: str):
        project = await self.collection.find_one({"project_id": project_id})
        
        if project:
            return Project(**project)
        
        new_project = Project(project_id=project_id)
        _ = await self.create_project(new_project)
        return new_project
    
    ## build with pagination with total no of documents.
    async def get_all_projects(self, page: int = 1, page_size: int = 10):
        total_documents = await self.collection.count_documents({})

        total_pages = (total_documents + page_size - 1) // page_size

        skip = (page - 1) * page_size

        cursor = self.collection.find().skip(skip).limit(page_size)
        projects = []
        async for document in cursor:
            projects.append(Project(**document))
        return projects, total_pages


