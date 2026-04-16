from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk
from .enums.DataBaseEnum import DatabaseEnum
from bson import ObjectId
from pymongo import InsertOne

class ChunkModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.COLLECTION_CHUNK_NAME.value]

# Add methods for chunk management here, e.g., create_chunk, get_chunk, delete_chunks_by_project_id, insert_many_chunks etc.

    async def create_chunk(self, chunk: DataChunk):
        chunk_dict = chunk.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(chunk_dict)
        return str(result.inserted_id)
    
    async def get_chunk(self, chunk_id: str):
        chunk = await self.collection.find_one({"_id": ObjectId(chunk_id)})
        if chunk:
            return DataChunk(**chunk)
        return None
    
    async def delete_chunks_by_project_id(self, project_id: str):
        result = await self.collection.delete_many({"chunk_project_id": project_id})
        return result.deleted_count
    
    # ude batching insert for inserting multiple chunks at once.
    async def insert_many_chunks(self, chunks: list[DataChunk], batch_size: int = 100):
        operations = []
        for chunk in chunks:
            chunk_dict = chunk.dict(by_alias=True, exclude_unset=True)
            operations.append(InsertOne(chunk_dict))
            if len(operations) == batch_size:
                await self.collection.bulk_write(operations)
                operations = []
        if operations:
            await self.collection.bulk_write(operations)
        return len(chunks)