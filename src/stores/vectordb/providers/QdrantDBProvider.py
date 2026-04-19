from ..VectorDBInterface import VectorDBInterface
from ..enums.VectorDBEnums import VectorDBEnums, DistanceMethodEnums
from qdrant_client import QdrantClient, models
import logging

class QdrantDBProvider(VectorDBInterface):
    
    def __init__(self, db_path: str, distance_method: str):
        self.db_path = db_path
        self.distance_method = None
        self.client = None

        self.logger = logging.getLogger(__name__)

        if distance_method == DistanceMethodEnums.COSINE.value: 
            self.distance_method = DistanceMethodEnums.COSINE.value
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = DistanceMethodEnums.DOT.value
        else:
            self.logger.error(f"Unsupported distance method: {distance_method}. Supported methods are: {[method.value for method in DistanceMethodEnums]}")
        

    def connect(self):
        self.client = QdrantClient(path=self.db_path)

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
    
    def is_collection_existed(self, collection_name: str) -> bool:
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return False
        
        return self.client.collection_exists(collection_name)
    def list_all_collections(self) -> list:
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return []
        return self.client.get_collections()

    def get_collection_info(self, collection_name: str) -> dict:
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return None
        
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return None
        
        return self.client.get_collection(collection_name)
    def delete_collection(self, collection_name: str):
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return
        
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return
        
        return self.client.delete_collection(collection_name)
    def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return
        
        if self.is_collection_existed(collection_name):
            if do_reset:
                self.logger.info(f"Collection {collection_name} already exists. Deleting and recreating it.")
                self.delete_collection(collection_name)
            else:
                self.logger.error(f"Collection {collection_name} already exists. Set do_reset=True to delete and recreate it.")
                return
        
        _ = self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=embedding_size,
                distance=self.distance_method
            )
        )
        return True
    def insert_one(self, collection_name: str, text: str, 
                          vector: list, metadata: dict = None, 
                          record_id: str = None):
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return
        try:
            _ = self.client.upload_records(
                collection_name=collection_name,
                records=[models.Record(
                    vector=vector,
                    payload=metadata
                )]
            )
        except Exception as e:
            self.logger.error(f"Failed to insert record into collection {collection_name}: {e}")
            return False
        return True
    
    def insert_many(self, collection_name: str, texts: list, 
                          vectors: list, metadata: list = None, 
                          record_ids: list = None, batch_size: int = 50):
        
        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = [None] * len(texts)

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size

            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]

            batch_records = [
                models.Record(
                    vector=batch_vectors[x],
                    payload={
                        "text": batch_texts[x], "metadata": batch_metadata[x]
                    }
                )

                for x in range(len(batch_texts))
            ]

            try:
                _ = self.client.upload_records(
                    collection_name=collection_name,
                    records=batch_records,
                )
            except Exception as e:
                self.logger.error(f"Error while inserting batch: {e}")
                return False

        return True

    def search_by_vector(self, collection_name: str, vector: list, limit: int = 5, 
                         filter: dict = None) -> list:
        if not self.client:
            self.logger.error("Qdrant client not initialized.")
            return []
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return []
        try:
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=filter
            )
        except Exception as e:
            self.logger.error(f"Failed to search in collection {collection_name}: {e}")
            return []
        
        return search_result