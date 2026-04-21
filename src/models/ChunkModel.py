# from .BaseDataModel import BaseDataModel
# from .minirag.schemes import DataChunk
# from .enums.DataBaseEnum import DatabaseEnum
# from bson import ObjectId
# from pymongo import InsertOne

# class ChunkModel(BaseDataModel):
#     def __init__(self, db_client):
#         super().__init__(db_client)
#         self.collection = self.db_client[DatabaseEnum.COLLECTION_CHUNK_NAME.value]

#     async def init_collection(self):
#         all_collections = await self.db_client.list_collection_names()
#         if DatabaseEnum.COLLECTION_CHUNK_NAME.value not in all_collections:
#             await self.db_client.create_collection(DatabaseEnum.COLLECTION_CHUNK_NAME.value)
#             # Create indexes for the collection
#             indexes = DataChunk.get_indexes()
#             for index in indexes:
#                 await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])
    
#     @classmethod
#     async def create_instance(cls, db_client):
#         instance = cls(db_client)
#         await instance.init_collection()
#         return instance

# # Add methods for chunk management here, e.g., create_chunk, get_chunk, delete_chunks_by_project_id, insert_many_chunks etc.

#     async def create_chunk(self, chunk: DataChunk):
#         chunk_dict = chunk.dict(by_alias=True, exclude_unset=True)
#         result = await self.collection.insert_one(chunk_dict)
#         return str(result.inserted_id)
    
#     async def get_chunk(self, chunk_id: str):
#         chunk = await self.collection.find_one({"_id": ObjectId(chunk_id)})
#         if chunk:
#             return DataChunk(**chunk)
#         return None
    
#     async def delete_chunks_by_project_id(self, project_id: str):
#         result = await self.collection.delete_many({"chunk_project_id": project_id})
#         return result.deleted_count
    
#     # ude batching insert for inserting multiple chunks at once.
#     async def insert_many_chunks(self, chunks: list[DataChunk], batch_size: int = 100):
#         operations = []
#         for chunk in chunks:
#             chunk_dict = chunk.dict(by_alias=True, exclude_unset=True)
#             operations.append(InsertOne(chunk_dict))
#             if len(operations) == batch_size:
#                 await self.collection.bulk_write(operations)
#                 operations = []
#         if operations:
#             await self.collection.bulk_write(operations)
#         return len(chunks)
    
#     async def get_project_chunks(self, project_id: str, page_no: int = 1, page_size: int = 50):
#         records = await self.collection.find({
#             "chunk_project_id": project_id
#         }).skip(
#             (page_no-1)*page_size
#         ).limit(page_size).to_list(length=None)

#         return[
#             DataChunk(**record)
#             for record in records
#         ]


from .BaseDataModel import BaseDataModel
from .minirag import DataChunk
from .enums.DataBaseEnum import DatabaseEnum
from bson.objectid import ObjectId
from pymongo import InsertOne
from sqlalchemy.future import select
from sqlalchemy import func, delete

class ChunkModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        return instance

    async def create_chunk(self, chunk: DataChunk):

        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
        return chunk

    async def get_chunk(self, chunk_id: str):

        async with self.db_client() as session:
            result = await session.execute(select(DataChunk).where(DataChunk.chunk_id == chunk_id))
            chunk = result.scalar_one_or_none()
        return chunk

    async def insert_many_chunks(self, chunks: list, batch_size: int=100):

        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i+batch_size]
                    session.add_all(batch)
            await session.commit()
        return len(chunks)

    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        async with self.db_client() as session:
            stmt = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(stmt)
            await session.commit()
        return result.rowcount
    
    async def get_poject_chunks(self, project_id: ObjectId, page_no: int=1, page_size: int=50):
        async with self.db_client() as session:
            stmt = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_no - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            records = result.scalars().all()
        return records
