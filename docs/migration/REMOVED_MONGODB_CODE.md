# Removed MongoDB Code Documentation

**Feature**: PostgreSQL Migration Cleanup  
**Date**: 2026-04-21  
**Commit**: `1d9cd23`  
**Branch**: `009-to-postgress`

This document preserves the MongoDB implementation that was removed during the PostgreSQL migration cleanup. This serves as historical reference and documentation of the original MongoDB-based architecture.

---

## Table of Contents

1. [MongoDB Model Classes](#mongodb-model-classes)
   - [AssetModel](#assetmodel)
   - [ChunkModel](#chunkmodel)
   - [ProjectModel](#projectmodel)
2. [MongoDB Pydantic Schemas](#mongodb-pydantic-schemas)
   - [Asset Schema](#asset-schema)
   - [DataChunk Schema](#datachunk-schema)
   - [Project Schema](#project-schema)
3. [MongoDB Connection Code](#mongodb-connection-code)
4. [Dependencies](#dependencies)
5. [Migration Notes](#migration-notes)

---

## MongoDB Model Classes

### AssetModel

**File**: `src/models/AssetModel.py` (lines 1-47, removed)

```python
from .BaseDataModel import BaseDataModel
from .minirag.schemes import Asset
from .enums.DataBaseEnum import DatabaseEnum
from bson import ObjectId

class AssetModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.COLLECTION_ASSET_NAME.value]

    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()
        if DatabaseEnum.COLLECTION_ASSET_NAME.value not in all_collections:
            await self.db_client.create_collection(DatabaseEnum.COLLECTION_ASSET_NAME.value)
            # Create indexes for the collection
            indexes = Asset.get_indexes()
            for index in indexes:
                await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])
    
    @classmethod
    async def create_instance(cls, db_client):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

    # Add methods for asset management here, e.g., create_asset, get_asset_by_id, get_assets_by_project_id, etc.

    async def create_asset(self, asset: Asset):
        asset_dict = asset.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(asset_dict)
        return result
    
    async def get_all_project_assets(self, asset_project_id: str, asset_type: str):
        cursor = await self.collection.find({"asset_project_id": ObjectId(asset_project_id) if isinstance(asset_project_id, str) else asset_project_id,
                                       "asset_type": asset_type}).to_list(length=None)
        
        return [Asset(**document) for document in cursor]
    
    async def get_asset_record(self, asset_project_id: str, asset_name: str):
        asset = await self.collection.find_one({"asset_project_id": ObjectId(asset_project_id) if isinstance(asset_project_id, str) else asset_project_id,
                                       "asset_name": asset_name})
        
        if asset:
            return Asset(**asset)
        
        return None
```

**Key Features**:
- Collection initialization with automatic index creation
- BSON ObjectId for document references
- Pydantic model serialization via `dict(by_alias=True, exclude_unset=True)`
- Factory pattern with `create_instance` classmethod

---

### ChunkModel

**File**: `src/models/ChunkModel.py` (lines 1-68, removed)

```python
from .BaseDataModel import BaseDataModel
from .minirag.schemes import DataChunk
from .enums.DataBaseEnum import DatabaseEnum
from bson import ObjectId
from pymongo import InsertOne

class ChunkModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.COLLECTION_CHUNK_NAME.value]

    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()
        if DatabaseEnum.COLLECTION_CHUNK_NAME.value not in all_collections:
            await self.db_client.create_collection(DatabaseEnum.COLLECTION_CHUNK_NAME.value)
            # Create indexes for the collection
            indexes = DataChunk.get_indexes()
            for index in indexes:
                await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])
    
    @classmethod
    async def create_instance(cls, db_client):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

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
    
    # Use batching insert for inserting multiple chunks at once.
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
    
    async def get_project_chunks(self, project_id: str, page_no: int = 1, page_size: int = 50):
        records = await self.collection.find({
            "chunk_project_id": project_id
        }).skip(
            (page_no-1)*page_size
        ).limit(page_size).to_list(length=None)

        return[
            DataChunk(**record)
            for record in records
        ]
```

**Key Features**:
- Bulk write operations with configurable batch size
- Pagination support via `skip()` and `limit()`
- String-based project_id for document queries
- MongoDB-specific `bulk_write()` with `InsertOne` operations

---

### ProjectModel

**File**: `src/models/ProjectModel.py` (lines 1-54, removed)

```python
from .BaseDataModel import BaseDataModel
from .minirag.schemes import Project
from .enums.DataBaseEnum import DatabaseEnum

class ProjectModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.collection = self.db_client[DatabaseEnum.COLLECTION_PROJECT_NAME.value]

    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()
        if DatabaseEnum.COLLECTION_PROJECT_NAME.value not in all_collections:
            await self.db_client.create_collection(DatabaseEnum.COLLECTION_PROJECT_NAME.value)
            # Create indexes for the collection
            indexes = Project.get_indexes()
            for index in indexes:
                await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])
    
    @classmethod
    async def create_instance(cls, db_client):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

    # Add methods for project management here, e.g., create_project, get_project_or_create_one, get_all_projects, etc.

    async def create_project(self, project: Project):
        project_dict = project.dict(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(project_dict)
        return result.inserted_id
    
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
```

**Key Features**:
- Get-or-create pattern for project management
- Pagination with total page calculation
- Async cursor iteration with `async for`
- String-based project_id as natural key

---

## MongoDB Pydantic Schemas

### Asset Schema

**File**: `src/models/minirag/schemes/asset.py` (lines 1-30, removed)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid import ObjectId
from datetime import datetime

class Asset(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    asset_project_id: ObjectId
    asset_name: str = Field(..., min_length=1)
    asset_type: str = Field(..., min_length=1)
    asset_size: int = Field(ge=0, default=None)
    asset_config: dict = Field(default=None)
    asset_pushed_date: datetime = Field(default=datetime.utcnow)
    
    @classmethod
    def get_indexes(cls):
        return [{
            "key": [("asset_project_id", 1)],
            "name": "asset_project_id_index_1",
            "unique": False
        },
        {
            "key": [("asset_project_id", 1), ("asset_name", 1)],
            "name": "asset_project_id_name_index_1",
            "unique": True
        }]

    class Config:
        arbitrary_types_allowed = True
```

**Key Features**:
- ObjectId type support via Pydantic config
- Compound unique index on (project_id, asset_name)
- Automatic timestamp with `datetime.utcnow`
- Field alias `_id` for MongoDB document ID

---

### DataChunk Schema

**File**: `src/models/minirag/schemes/data_chunk.py` (lines 1-22, removed)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid import ObjectId

class DataChunk(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    chunk_text: str = Field(..., min_length=1)
    chunk_metadata: dict
    chunk_order: int = Field(..., gt=0)
    chunk_project_id: ObjectId
    chunk_asset_id: Optional[ObjectId]

    @classmethod
    def get_indexes(cls):
        return [{
            "key": [("chunk_project_id", 1)],
            "name": "chunk_project_id_index_1",
            "unique": False
        }]

    class Config:
        arbitrary_types_allowed = True
```

**Key Features**:
- Flexible metadata storage as dict
- Optional asset relationship
- Index on project_id for efficient queries
- Positive integer validation for chunk_order

---

### Project Schema

**File**: `src/models/minirag/schemes/project.py` (lines 1-25, removed)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid import ObjectId

class Project(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    project_id: str = Field(..., min_length=1)

    @validator('project_id')
    def validate_project_id(cls, value):
        if not value.isalnum():
            raise ValueError('project_id must be alphanumeric')
        
        return value
    
    @classmethod
    def get_indexes(cls):
        return [{
            "key": [("project_id", 1)],
            "name": "project_id_index_1",
            "unique": True
        }]

    class Config:
        arbitrary_types_allowed = True
```

**Key Features**:
- Custom validator for alphanumeric project_id
- Unique index on project_id
- Minimal schema for flexibility
- String-based natural key

---

## MongoDB Connection Code

### Application Startup

**File**: `src/main.py` (removed sections)

```python
# Import (line 7)
from motor.motor_asyncio import AsyncIOMotorClient

# Startup event (lines 21-22)
@app.on_event("startup")
async def startup_span():
    settings = get_settings()
    
    # Initialize your database client here
    app.mongo_conn = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongo_conn[settings.MONGODB_DATABASE]
    
    # ... rest of initialization

# Shutdown event (line 48)
@app.on_event("shutdown")
async def shutdown_span():
    app.mongo_conn.close()
    app.vectordb_client.disconnect()
    logger.info("MongoDB connection closed.")
```

**Key Features**:
- Motor async MongoDB driver
- Connection pooling via AsyncIOMotorClient
- Database selection via bracket notation
- Graceful connection closure on shutdown

---

## Dependencies

### Removed from requirements.txt

```txt
motor==3.4.0           # MongoDB async driver
pymongo==4.6.3         # MongoDB synchronous driver
pydantic-mongo==2.3.0  # Pydantic-MongoDB integration
```

**Why These Were Needed**:
- **motor**: Async/await support for MongoDB operations
- **pymongo**: Core MongoDB driver (motor dependency)
- **pydantic-mongo**: Seamless integration between Pydantic models and MongoDB documents

---

## Migration Notes

### Key Differences: MongoDB vs PostgreSQL

| Aspect | MongoDB | PostgreSQL |
|--------|---------|------------|
| **ID Type** | ObjectId (12-byte) | Integer (auto-increment) |
| **Schema** | Flexible, schemaless | Rigid, defined via SQLAlchemy |
| **Relationships** | Manual ObjectId references | Foreign keys with constraints |
| **Queries** | Dictionary-based filters | SQL via SQLAlchemy ORM |
| **Indexes** | Created programmatically | Defined in model `__table_args__` |
| **Transactions** | Session-based | Async context managers |
| **Bulk Ops** | `bulk_write()` with operations | `session.add_all()` |
| **Pagination** | `.skip().limit()` | `.offset().limit()` |

### Why We Migrated

1. **Relational Integrity**: PostgreSQL foreign keys ensure data consistency
2. **Type Safety**: Integer IDs vs string ObjectIds reduce type conversion errors
3. **ACID Compliance**: Better transaction support for critical operations
4. **Indexing**: More sophisticated index types (GIN, GiST for full-text)
5. **Ecosystem**: Better integration with analytics and BI tools

### What Was Preserved

- ✅ All API endpoints remain unchanged
- ✅ Same business logic and workflows
- ✅ Pagination functionality
- ✅ Bulk insert operations
- ✅ Get-or-create patterns
- ✅ Project/Asset/Chunk relationships

### Data Migration (Out of Scope)

This code cleanup did **not** include data migration. If you need to migrate existing MongoDB data:

1. Export MongoDB collections to JSON:
   ```bash
   mongoexport --db=minirag --collection=projects --out=projects.json
   mongoexport --db=minirag --collection=assets --out=assets.json
   mongoexport --db=minirag --collection=chunks --out=chunks.json
   ```

2. Transform ObjectIds to integers and adjust schema

3. Import into PostgreSQL using SQLAlchemy bulk operations

4. Run Alembic migrations to ensure schema consistency

---

## Historical Context

**Timeline**:
- MongoDB implementation: Original architecture
- PostgreSQL implementation: Commit `5990885` (2026-04-21)
- MongoDB code cleanup: Commit `1d9cd23` (2026-04-21)

**Total Lines Removed**: 271 lines
- Model classes: 169 lines
- Pydantic schemas: 77 lines
- Connection code: 4 lines
- Dependencies: 3 lines
- Import statements: 18 lines

---

## Rollback Procedure (If Needed)

If you need to restore MongoDB functionality:

1. Revert commit: `git revert 1d9cd23`
2. Restore dependencies: Reinstall motor, pymongo, pydantic-mongo
3. Update main.py to use MongoDB connection
4. Restore model implementations from this document
5. Test all endpoints thoroughly

**Note**: The PostgreSQL implementation would need to be disabled or removed separately.

---

**Document Version**: 1.0  
**Last Updated**: 2026-04-21  
**Maintained By**: Development Team
