from fastapi import FastAPI
from routes import base, data
from stores import LLMProviderFactory
from stores import VectorDBProviderFactory
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.on_event("startup")
async def startup_span():
    settings = get_settings()
    # Initialize your database client here
    app.mongo_conn = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongo_conn[settings.MONGODB_DATABASE]

    llm_provider_factory = LLMProviderFactory(config=settings)

    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

    vectordb_provider_factory = VectorDBProviderFactory(config=settings)
    app.vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    app.vectordb_client.connect()



@app.on_event("shutdown")
async def shutdown_span():
    app.mongo_conn.close()
    app.vectordb_client.disconnect()
    logger.info("MongoDB connection closed.")




app.include_router(base.base_router)
app.include_router(data.data_router)