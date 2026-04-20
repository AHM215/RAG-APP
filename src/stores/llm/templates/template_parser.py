import os
from typing import List, Any
from langchain_core.prompts import ChatPromptTemplate

class TemplateParser:

    def __init__(self, language: str=None, default_language='en'):
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.default_language = default_language
        self.language = None

        self.set_language(language)

    
    def set_language(self, language: str):
        if not language:
            self.language = self.default_language

        language_path = os.path.join(self.current_path, "locales", language)
        if os.path.exists(language_path):
            self.language = language
        else:
            self.language = self.default_language

    def get(self, group: str, key: str, vars: dict={}):
        if not group or not key:
            return None
        
        group_path = os.path.join(self.current_path, "locales", self.language, f"{group}.py" )
        targeted_language = self.language
        if not os.path.exists(group_path):
            group_path = os.path.join(self.current_path, "locales", self.default_language, f"{group}.py" )
            targeted_language = self.default_language

        if not os.path.exists(group_path):
            return None
        
        # import group module
        module = __import__(f"stores.llm.templates.locales.{targeted_language}.{group}", fromlist=[group])

        if not module:
            return None
        
        key_attribute = getattr(module, key)
        return key_attribute.substitute(vars)

    def get_chat_prompt(self, group: str, key: str) -> ChatPromptTemplate:
        """Get a LangChain ChatPromptTemplate for the specified group and key.
        
        Args:
            group: Template group name (e.g., 'rag')
            key: Template key (e.g., 'rag_prompt')
            
        Returns:
            ChatPromptTemplate object with the locale-specific template
            
        Raises:
            ValueError: If group or key is invalid
            FileNotFoundError: If the locale module is not found
        """
        if not group or not key:
            raise ValueError("Both group and key must be provided")
        
        group_path = os.path.join(self.current_path, "locales", self.language, f"{group}.py")
        targeted_language = self.language
        if not os.path.exists(group_path):
            group_path = os.path.join(self.current_path, "locales", self.default_language, f"{group}.py")
            targeted_language = self.default_language

        if not os.path.exists(group_path):
            raise FileNotFoundError(f"Template module not found: {group}")
        
        module = __import__(f"stores.llm.templates.locales.{targeted_language}.{group}", fromlist=[group])

        if not module:
            raise FileNotFoundError(f"Failed to import module: {group}")
        
        template = getattr(module, key, None)
        if template is None:
            raise ValueError(f"Template key '{key}' not found in group '{group}'")
            
        return template

    def format_documents(self, documents: List[Any]) -> str:
        """Format a list of retrieved documents for context injection.
        
        Args:
            documents: List of document objects with .text attribute
            
        Returns:
            Formatted string with numbered documents suitable for {context} placeholder
        """
        if not documents or len(documents) == 0:
            return "No documents were retrieved."
        
        group_path = os.path.join(self.current_path, "locales", self.language, "rag.py")
        targeted_language = self.language
        if not os.path.exists(group_path):
            group_path = os.path.join(self.current_path, "locales", self.default_language, "rag.py")
            targeted_language = self.default_language
        
        module = __import__(f"stores.llm.templates.locales.{targeted_language}.rag", fromlist=["rag"])
        format_document = getattr(module, "format_document")
        
        formatted_docs = [
            format_document(idx + 1, doc.text)
            for idx, doc in enumerate(documents)
        ]
        
        return "\n\n".join(formatted_docs)