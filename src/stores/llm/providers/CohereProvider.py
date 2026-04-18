from ..LLMInterface import LLMInterface
from ..enums import CoHereEnums, SystemPromptEnum, DocumentTypeEnum
import cohere
import logging

class CohereProvider(LLMInterface):
    
    def __init__(self, api_key: str,
                default_input_max_characters: int=1000,
                default_generation_max_output_tokens: int=1000,
                default_generation_temperature: float=0.1):
        self.api_key = api_key

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.default_system_prompt = SystemPromptEnum.DEFAULT_SYSTEM_PROMPT.value

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = cohere.Client(api_key=self.api_key)

        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_name: str):
        self.generation_model_id = model_name
        self.logger.info(f"Set generation model to {model_name}")

    def set_embedding_model(self, model_name: str, embedding_size: int):
        self.embedding_model_id = model_name
        self.embedding_size = embedding_size
        self.logger.info(f"Set embedding model to {model_name} with size {embedding_size}")

    def generate_text(self, prompt: str, chat_history: list = [], temperature: float = None, 
                      max_output_tokens: int = None):
        if not self.client:
            self.logger.error("Cohere client not initialized.")
            return None
        if not self.generation_model_id:
            self.logger.error("Generation model not set.")
            return None
        
        if not chat_history:
            chat_history = [self.construct_prompt(self.default_system_prompt, role=CoHereEnums.SYSTEM.value)]
        
        temperature = temperature if temperature else self.default_generation_temperature
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens

        response = self.client.chat(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=self.process_text(prompt),
            temperature=temperature,
            max_tokens=max_output_tokens
        )
        if not response or not response.text:
            self.logger.error("No response from Cohere API.")
            return None
        
        return response.text
    
    def embed_text(self, text: str, document_type: str = None):
        if not self.client:
            self.logger.error("Cohere client not initialized.")
            return None
        if not self.embedding_model_id:
            self.logger.error("Embedding model not set.")
            return None
        
        input_type = CoHereEnums.DOCUMENT.value
        if document_type == DocumentTypeEnum.QUERY.value:
            input_type = CoHereEnums.QUERY.value

        response = self.client.embed(
            model=self.embedding_model_id,
            texts=[text],
            input_type=input_type,
            embedding_types=['float']
        )
        if not response or not response.embeddings or not response.embeddings.float:
            self.logger.error("No response from Cohere API for embedding.")
            return None
        
        return response.embeddings.float[0]
    
    def construct_prompt(self, query: str, role: str = None, chat_history: list = []):
        if role:
            chat_history.append({"role": role, "content": self.process_text(query)})
        else:
            chat_history.append({"role": CoHereEnums.USER.value, "content": self.process_text(query)})
        return chat_history
        
    def process_text(self, text: str):
        if len(text) > self.default_input_max_characters:
            self.logger.warning(f"Input text exceeds maximum character limit of {self.default_input_max_characters}. Truncating input.")
            return text[:self.default_input_max_characters].strip()
        return text.strip()
        
