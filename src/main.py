from fastapi import FastAPI
from routes import base, data, nlp
from stores import LLMProviderFactory, VectorDBProviderFactory
from stores import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from helpers.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.on_event("startup")
async def startup_span():
    settings = get_settings()
    
    # Database setup
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(app.db_engine, class_=AsyncSession, 
                                 expire_on_commit=False)

    # LLM providers
    llm_provider_factory = LLMProviderFactory(config=settings)
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

    # Vector DB
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=app.db_client)
    app.vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await app.vectordb_client.connect()

    # Template parser
    app.template_parser = TemplateParser(language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG)

    # Cross-encoder reranker (load once at startup)
    app.cross_encoder = None
    if settings.RERANKER_MODE == "cross_encoder":
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading cross-encoder model: {settings.RERANKER_MODEL}")
            app.cross_encoder = CrossEncoder(
                settings.RERANKER_MODEL,
                max_length=512
            )
            logger.info("Cross-encoder loaded successfully")
        except ImportError:
            logger.error(
                "RERANKER_MODE=cross_encoder requires sentence-transformers. "
                "Install with: pip install sentence-transformers"
            )
            raise


@app.on_event("shutdown")
async def shutdown_span():
    app.vectordb_client.disconnect()
    logger.info("Application shutdown complete.")


app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)