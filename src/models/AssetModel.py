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