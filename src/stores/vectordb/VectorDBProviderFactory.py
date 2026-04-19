from providers import QdrantDBProvider
from .enums.VectorDBEnums import VectorDBEnums
from controllers.BaseController import BaseController
import os

class VectorDBProviderFactory:
    def __init__(self, config: dict):
        self.config = config
        self.base_controller = BaseController()

    def create(self, provider: str):
        if provider == VectorDBEnums.QDRANT.value:
            db_path = self.base_controller.get_database_path(db_name=self.config.VECTOR_DB_NAME)
            return QdrantDBProvider(db_path=db_path, 
                                    distance_method=self.config.VECTOR_DB_DISTANCE_METHOD)
        else:
            raise ValueError(f"Unsupported vector database provider: {provider}. Supported providers are: {[provider.value for provider in VectorDBEnums]}")