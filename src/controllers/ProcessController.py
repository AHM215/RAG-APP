from fastapi import status
from fastapi.responses import JSONResponse
from .BaseController import BaseController
from .ProjectController import ProjectController
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from models import ProcessingEnum
import os



class ProcessController(BaseController):

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1]

    def get_file_loader(self, file_id: str):
        ## check if file exists from ProcessingEnum is txt or pdf to return the custom loader
        file_path = os.path.join(self.project_path, file_id)
        file_ext = self.get_file_extension(file_id=file_id)

        if file_ext == ProcessingEnum.TXT.value:
            return TextLoader(file_path, encoding = "utf-8")
        elif file_ext == ProcessingEnum.PDF.value:
            return PyMuPDFLoader(file_path)
        else:
            # use fastapi response to return error message with status code 400
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": f"Unsupported file type: {file_ext}"
                }
            )
        
    def get_file_content(self, file_id: str):
        loader = self.get_file_loader(file_id=file_id)
        if isinstance(loader, JSONResponse):
            return loader
        return loader.load()
    
    def process_file_content(self, file_content: list, file_id: str, 
                             chunk_size: int = 100, overlap_size : int = 20):
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, 
                                                       chunk_overlap=overlap_size,
                                                       length_function=len)
        
        file_content_texts = [doc.page_content for doc in file_content]

        file_content_metadata = [doc.metadata for doc in file_content]

        chunks = text_splitter.create_documents(file_content_texts, file_content_metadata)

        return chunks        
    