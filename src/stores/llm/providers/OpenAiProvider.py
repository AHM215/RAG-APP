from ..LLMEnterface import LLMInterface
from ..enums import LLMEnums
from openai import OpenAI
import logging

class OpenAIProvider(LLMInterface):

    def __init__(self, api_url: str, api_key: str,
                default_input_max_characters: int=1000,
                default_generation_max_output_tokens: int=1000,
                default_generation_temperature: float=0.1):
        self.api_key = api_key
        self.api_url = api_url

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature
        self.default_system_prompt = LLMEnums.DEFAULT_SYSTEM_PROMPT.value

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = OpenAI(api_key=self.api_key, api_url=self.api_url)

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
            self.logger.error("OpenAI client not initialized.")
            return None
        if not self.generation_model_id:
            self.logger.error("Generation model not set.")
            return None
        
        if not chat_history:
            chat_history = [self.construct_prompt(self.default_system_prompt, role=LLMEnums.SYSTEM.value)]
        
        temperature = temperature if temperature else self.default_generation_temperature
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens

        self.chat_history = self.construct_prompt(prompt, chat_history=chat_history)[-1]

        response = self.client.chat.completions.create(
            model=self.generation_model_id,
            messages=chat_history,
            temperature=temperature,
            max_tokens=max_output_tokens
        )

        if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message:
            self.logger.error("No response from OpenAI API.")
            return None
        
        return response.choices[0].message.content.strip()
    
    def embed_text(self, text: str, document_type: str = None):
        if not self.client:
            self.logger.error("OpenAI client not initialized.")
            return None
        if not self.embedding_model_id:
            self.logger.error("Embedding model not set.")
            return None
        
        response = self.client.embeddings.create(
            model=self.embedding_model_id,
            input=text
        )

        if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
            self.logger.error("No embedding response from OpenAI API.")
            return None
        
        return response.data[0].embedding
    
    def construct_prompt(self, query: str, role: str = None, chat_history: list = []):
        if role:
            chat_history.append({"role": role, "content": self.process_text(query)})
        else:
            chat_history.append({"role": LLMEnums.USER.value, "content": self.process_text(query)})
        return chat_history
    
    def process_text(self, text: str):
        if len(text) > self.default_input_max_characters:
            self.logger.warning(f"Input text exceeds maximum character limit of {self.default_input_max_characters}. Truncating input.")
            return text[:self.default_input_max_characters]
        return text