from fastapi.responses import JSONResponse
from .BaseController import BaseController
from models import Project, DataChunk
from stores.llm.enums import DocumentTypeEnum
from models import ResponseSignal
from typing import List
import os
import json

class NLPController(BaseController):
    def __init__(self, vectordb_client, generation_client, embedding_client):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        # self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()

    def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project.project_id)
        return self.vectordb_client.delete_collection(collection_name)

    def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project.project_id)
        collection_info = self.vectordb_client.get_collection_info(collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )


    def index_into_vector_db(self, project: Project, chunks: List[DataChunk], 
                             chunks_ids: List[int], do_reset: bool = False):
        
        collection_name = self.create_collection_name(project.project_id)
        
        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]

        vectors = [
            self.embedding_client.embed_text(text, DocumentTypeEnum.DOCUMENT.value)
            for text in texts
        ]

        _ = self.vectordb_client.create_collection(collection_name, self.embedding_client.embedding_size, do_reset)

        _ = self.vectordb_client.insert_many(collection_name, texts, vectors, metadata, record_ids=chunks_ids)
        
        return True


    def search_vector_db_collection(self, project: Project, text: str , limit: int = 10):
        collection_name = self.create_collection_name(project.project_id)

        is_existed = self.vectordb_client.is_collection_existed(collection_name)
        if not is_existed:
            return False

        vector = self.embedding_client.embed_text(text, DocumentTypeEnum.QUERY.value)

        if not vector or len(vector) == 0:
            return False
        


        results = self.vectordb_client.search_by_vector(collection_name, vector, limit)

        if not results:
            return False

        return results



    def aswer_rag_question(self, project: Project, query: str, limit: int = 10):
        pass
