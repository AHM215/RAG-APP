from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.enums import DocumentTypeEnum, OpenAIEnums, CoHereEnums
from typing import List
import json

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()
    
    def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return self.vectordb_client.delete_collection(collection_name=collection_name)
    
    def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        vectors = [
            self.embedding_client.embed_text(text=text, 
                                             document_type=DocumentTypeEnum.DOCUMENT.value)
            for text in texts
        ]

        # step3: create collection if not exists
        _ = self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        _ = self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        vector = self.embedding_client.embed_text(text=text, 
                                                 document_type=DocumentTypeEnum.QUERY.value)

        if not vector or len(vector) == 0:
            return False

        # step3: do semantic search
        results = self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit
        )

        if not results:
            return False

        return results
    
    def _convert_messages_for_provider(self, messages: List) -> List[dict]:
        """Convert LangChain messages to provider-specific format using dynamic enum mapping.
        
        Args:
            messages: List of LangChain message objects
            
        Returns:
            List of dict messages in provider-specific format
        """
        provider_messages = []
        provider_enums = self.generation_client.enums
        
        # Map LangChain message types to provider roles
        role_mapping = {
            'system': provider_enums.SYSTEM.value,
            'human': provider_enums.USER.value,
            'user': provider_enums.USER.value,
            'assistant': provider_enums.ASSISTANT.value,
        }
        
        for message in messages:
            msg_dict = message.dict() if hasattr(message, 'dict') else message
            langchain_role = msg_dict.get('type', msg_dict.get('role', 'user'))
            content = msg_dict.get('content', '')
            
            # Map to provider-specific role
            provider_role = role_mapping.get(langchain_role.lower(), provider_enums.USER.value)
            
            # Use provider-specific format
            if provider_enums == CoHereEnums:
                provider_messages.append({
                    "role": provider_role,
                    "text": content
                })
            else:
                provider_messages.append({
                    "role": provider_role,
                    "content": content
                })
        
        return provider_messages

    def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        
        answer, full_prompt, chat_history = None, None, None

        # step1: retrieve related documents
        retrieved_documents = self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history
        
        # step2: Format documents as context
        context = self.template_parser.format_documents(retrieved_documents)

        # step3: Get LangChain ChatPromptTemplate
        prompt_template = self.template_parser.get_chat_prompt("rag", "rag_prompt")

        # step4: Format the template with context and question
        messages = prompt_template.format_messages(context=context, question=query)

        # step5: Convert to provider format
        chat_history = self._convert_messages_for_provider(messages)

        # step6: Generate answer (empty prompt since messages are in chat_history)
        answer = self.generation_client.generate_text(
            prompt="",
            chat_history=chat_history
        )

        # For backward compatibility, store the formatted context as full_prompt
        full_prompt = context

        return answer, full_prompt, chat_history
