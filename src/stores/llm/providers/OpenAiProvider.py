from ..LLMInterface import LLMInterface
from ..enums import OpenAIEnums
from openai import OpenAI
import httpx
import logging
import time
from typing import List, Union
import asyncio


class _RateLimitTransport(httpx.HTTPTransport):
    def __init__(self, delay_s: float = 1.5, **kwargs):
        super().__init__(**kwargs)
        self._delay_s = float(delay_s)
        self._last = 0.0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._delay_s:
            time.sleep(self._delay_s - elapsed)
        self._last = time.monotonic()
        return super().handle_request(request)


class OpenAIProvider(LLMInterface):

    def __init__(self, api_key: str, api_url: str=None,
                       default_input_max_characters: int=1000,
                       default_generation_max_output_tokens: int=1000,
                       default_generation_temperature: float=0.1):
        
        self.api_key = api_key
        self.api_url = api_url

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None

        self.embedding_model_id = None
        self.embedding_size = None

        transport = _RateLimitTransport(delay_s=1.5)
        http_client = httpx.Client(transport=transport)
        self.client = OpenAI(
            api_key = self.api_key,
            base_url = self.api_url if self.api_url and len(self.api_url) else None,
            http_client = http_client,
        )

        self.enums = OpenAIEnums
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    async def generate_text(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                            temperature: float = None):
        
        if not self.client:
            self.logger.error("OpenAI client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return None
        
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_generation_max_output_tokens
        temperature = temperature if temperature else self.default_generation_temperature

        messages = list(chat_history or [])
        if prompt:
            messages.append(
                self.construct_prompt(prompt=prompt, role=OpenAIEnums.USER.value)
            )

        response = await asyncio.to_thread(
                                    self.client.chat.completions.create,  # ← pass the function, not the call
                                    model=self.generation_model_id,
                                    messages=messages,
                                    max_tokens=max_output_tokens,
                                    temperature=temperature
                                )

        if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message:
            self.logger.error("Error while generating text with OpenAI")
            return None

        return response.choices[0].message.content


    def embed_text(self, text: Union[str, List[str]], document_type: str = None):
        
        if not self.client:
            self.logger.error("OpenAI client was not set")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model for OpenAI was not set")
            return None
        
        if isinstance(text, str):
            text = [text]
        
        response = self.client.embeddings.create(
            model = self.embedding_model_id,
            input = text,
        )

        if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
            self.logger.error("Error while embedding text with OpenAI")
            return None

        return [r.embedding for r in response.data]

    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": self.process_text(prompt)
        }
    


    
