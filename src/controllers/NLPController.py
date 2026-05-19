from .BaseController import BaseController
from models.minirag.schemes import Project, DataChunk, RetrievedDocument
from stores.llm.enums import DocumentTypeEnum, OpenAIEnums, CoHereEnums
from helpers.config import get_settings
from typing import List, Tuple
import json
import asyncio
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

QUERY_ADAPTER_MODES = {"none", "rewrite", "hyde"}
RERANKER_MODES = {"none", "cross_encoder", "llm"}

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser, cross_encoder):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.cross_encoder = cross_encoder
        logger.info("NLPController initialized")

    def create_collection_name(self, project_id: int):
        name = f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
        logger.debug(f"Collection name created: '{name}' for project_id={project_id}")
        return name
    
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        logger.info(f"Resetting vector DB collection: '{collection_name}'")
        result = await self.vectordb_client.delete_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' reset complete")
        return result
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        logger.info(f"Fetching collection info for: '{collection_name}'")
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)
        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)
        logger.info(f"Indexing {len(chunks)} chunks into '{collection_name}' (do_reset={do_reset})")

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in chunks]
        logger.debug(f"Embedding {len(texts)} texts")
        vectors = self.embedding_client.embed_text(text=texts, 
                                             document_type=DocumentTypeEnum.DOCUMENT.value)
        logger.debug(f"Embeddings generated: {len(vectors)} vectors")

        # step3: create collection if not exists
        logger.debug(f"Creating collection '{collection_name}' if not exists")
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        logger.debug(f"Inserting {len(texts)} records into '{collection_name}'")
        _ = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        logger.info(f"Indexing complete for '{collection_name}': {len(chunks)} chunks inserted")
        return True
    
    # ==================== QUERY ADAPTATION ====================

    async def _rewrite_query(self, query: str) -> str:
        """Rewrite query to be more search-friendly using LLM."""
        try:
            logger.info(f"Rewriting query: '{query}'")
            rewrite_prompt = self.template_parser.get_chat_prompt("query_adapter", "rewrite_prompt")
            messages = rewrite_prompt.format_messages(query=query)
            chat_history = self._convert_messages_for_provider(messages)
            logger.debug(f"Chat history prepared with {len(chat_history)} messages")
            rewritten = await self.generation_client.generate_text(
                prompt="",
                chat_history=chat_history,
                temperature=0,
                max_output_tokens=256
            )
            rewritten = rewritten.strip()
            if rewritten:
                logger.debug(f"Query rewritten: '{query}' -> '{rewritten}'")
                return rewritten
            logger.warning(f"Rewrite returned empty, using original: '{query}'")

        except Exception as e:
            logger.error(f"Query rewrite failed, using original: '{query}' | Error: {e}", exc_info=True)
        
        return query

    async def _hyde_query(self, query: str) -> str:
        """Generate hypothetical document for HyDE retrieval."""
        try:
            logger.info(f"Generating HyDE document for query: '{query}'")
            hyde_prompt = self.template_parser.get_chat_prompt("query_adapter", "hyde_prompt")
            messages = hyde_prompt.format_messages(query=query)
            chat_history = self._convert_messages_for_provider(messages)
            logger.debug(f"HyDE chat history prepared with {len(chat_history)} messages")
            
            hypothetical = await self.generation_client.generate_text(
                prompt="",
                chat_history=chat_history,
                temperature=0.7,
                max_output_tokens=512
            )
            
            hypothetical = hypothetical.strip()
            if hypothetical:
                logger.debug(f"HyDE document generated for: '{query}' -> '{hypothetical[:80]}...'")
                return hypothetical
            logger.warning(f"HyDE returned empty, using original: '{query}'")

        except Exception as e:
            logger.error(f"HyDE generation failed, using original: '{query}' | Error: {e}", exc_info=True)
        
        return query

    async def _adapt_query(self, query: str, adapter_mode: str = None) -> Tuple[str, str]:
        mode = adapter_mode or settings.QUERY_ADAPTER_MODE
        if mode not in QUERY_ADAPTER_MODES:
            logger.warning(f"Unknown query adapter mode '{mode}', using 'none'")
            mode = "none"

        logger.info(f"Adapting query with mode='{mode}': '{query}'")
        
        if mode == "rewrite":
            adapted = await self._rewrite_query(query)
            return adapted, query
        elif mode == "hyde":
            adapted = await self._hyde_query(query)
            return adapted, query
        else:
            logger.debug(f"No query adaptation (mode='{mode}')")
            return query, query

    # ==================== VECTOR SEARCH ====================

    async def _raw_vector_search(self, project: Project, text: str, 
                                  limit: int) -> List[RetrievedDocument]:
        """Perform raw vector similarity search without reranking."""
        collection_name = self.create_collection_name(project_id=project.project_id)
        logger.info(f"Vector search in '{collection_name}' | limit={limit} | query='{text[:80]}'")

        vectors = self.embedding_client.embed_text(
            text=text, 
            document_type=DocumentTypeEnum.QUERY.value
        )

        if not vectors or len(vectors) == 0:
            logger.warning(f"Embedding returned empty for query: '{text[:80]}'")
            return []
        
        query_vector = vectors[0] if isinstance(vectors, list) else vectors

        if not query_vector:
            logger.warning("Query vector is None after embedding")
            return []

        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        logger.info(f"Vector search returned {len(results) if results else 0} results")
        return results if results else []

    # ==================== RERANKING ====================

    async def _cross_encoder_rerank(self, query: str, 
                                     candidates: List[RetrievedDocument],
                                     top_k: int) -> List[RetrievedDocument]:
        """Rerank candidates using cross-encoder model."""
        if not self.cross_encoder or not candidates:
            logger.warning(f"Cross-encoder rerank skipped: cross_encoder={bool(self.cross_encoder)}, candidates={len(candidates)}")
            return candidates[:top_k]

        logger.info(f"Cross-encoder reranking {len(candidates)} candidates, top_k={top_k}")
        pairs = [(query, doc.text) for doc in candidates]

        try:
            scores: List[float] = await asyncio.to_thread(
                self.cross_encoder.predict, pairs
            )
        except Exception as e:
            logger.error(f"Cross-encoder rerank failed: {e}", exc_info=True)
            return candidates[:top_k]
        
        for doc, score in zip(candidates, scores):
            doc.rerank_score = float(score)
        
        reranked = sorted(candidates, key=lambda d: d.rerank_score or 0, reverse=True)
        logger.debug(f"Cross-encoder reranking complete, top score={reranked[0].rerank_score:.4f}" if reranked else "No results after reranking")
        return reranked[:top_k]

    async def _llm_rerank(self, query: str,
                          candidates: List[RetrievedDocument],
                          top_k: int) -> List[RetrievedDocument]:

        if not candidates:
            return []

        logger.info(f"LLM reranking {len(candidates)} candidates, top_k={top_k}")

        numbered = "\n".join(
            f"[{i}] {doc.text[:600]}" for i, doc in enumerate(candidates)
        )

        rerank_prompt = self.template_parser.get_chat_prompt("rerank", "rerank_prompt")
        messages = rerank_prompt.format_messages(query=query, passages=numbered)
        chat_history = self._convert_messages_for_provider(messages)

        try:
            raw = await self.generation_client.generate_text(
                prompt="",
                chat_history=chat_history,
                temperature=0,
                max_output_tokens=256
            )

            raw = raw.strip()
            start = raw.find("[")
            end = raw.rfind("]")
            if start == -1 or end == -1 or end < start:
                raise ValueError("LLM response does not contain a JSON array")

            order: List[int] = json.loads(raw[start:end + 1])
            logger.info(
                "LLM rerank mapping: " +
                " | ".join([f"{rank}:{idx}" for rank, idx in enumerate(order)])
            )
            score_map = {}
            seen = set()
            valid_order = []

            for rank, idx in enumerate(order):
                if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen:
                    seen.add(idx)
                    valid_order.append(idx)

            n = len(valid_order)
            for rank, idx in enumerate(valid_order):
                score_map[idx] = (n - rank) / n if n else 0.0

            for i, doc in enumerate(candidates):
                doc.rerank_score = score_map.get(i, 0.0)

            reranked = sorted(
                candidates,
                key=lambda d: d.rerank_score or 0,
                reverse=True
            )

        except (json.JSONDecodeError, IndexError, TypeError, ValueError) as e:
            logger.error(f"LLM rerank failed: {e}", exc_info=True)
            reranked = candidates

        return reranked[:top_k]
    # ==================== CENTRAL RETRIEVAL PIPELINE ====================

    async def _retrieve_and_rerank(self, project: Project, query: str,
                                    candidates_n: int = None,
                                    top_k: int = None,
                                    force_rerank: bool = None,
                                    query_adapter: str = None) -> List[RetrievedDocument]:

        logger.info(f"Retrieval pipeline start | project={project.project_id} | query='{query[:80]}' | adapter={query_adapter} | force_rerank={force_rerank}")

        # Step 1: Query adaptation
        search_query, original_query = await self._adapt_query(query, query_adapter)
        
        # Step 2: Determine reranker mode
        reranker_mode = settings.RERANKER_MODE

        if isinstance(force_rerank, str):
            reranker_mode = force_rerank
        
        if force_rerank is False:
            reranker_mode = "none"
            logger.debug("Reranking disabled by force_rerank=False")
        elif force_rerank is True and reranker_mode == "none":
            reranker_mode = "cross_encoder" if self.cross_encoder else "llm"
            logger.debug(f"Reranking forced, selected mode: '{reranker_mode}'")

        if reranker_mode not in RERANKER_MODES:
            logger.warning(f"Unknown reranker mode '{reranker_mode}', using 'none'")
            reranker_mode = "none"

        final_top_k = top_k or settings.CONTEXT_TOP_K
        fetch_n = (candidates_n or settings.RETRIEVAL_CANDIDATES_N) if reranker_mode != "none" else final_top_k
        logger.debug(f"reranker_mode='{reranker_mode}' | fetch_n={fetch_n} | final_top_k={final_top_k}")

        # Step 3: Vector search
        candidates = await self._raw_vector_search(project, search_query, limit=fetch_n)
        logger.info(f"Retrieved {len(candidates)} candidates before reranking")

        # Step 4: Reranking
        if reranker_mode == "cross_encoder":
            results = await self._cross_encoder_rerank(original_query, candidates, final_top_k)
        elif reranker_mode == "llm":
            results = await self._llm_rerank(original_query, candidates, final_top_k)
        else:
            results = candidates[:final_top_k]

        logger.info(f"Retrieval pipeline complete | returned {len(results)} documents")
        return results

    async def batch_search(self, project: Project, queries: List[str],
                           limit: int = 10,
                           candidates_n: int = None,
                           top_k: int = None,
                           rerank: str = None,
                           query_adapter: str = None):

        logger.info(f"batch_search | project={project.project_id} | queries={len(queries)} | limit={limit} | rerank={rerank} | adapter={query_adapter}")

        adapted_queries = []
        for q in queries:
            adapted, _ = await self._adapt_query(q, query_adapter)
            adapted_queries.append(adapted)

        collection_name = self.create_collection_name(project_id=project.project_id)
        logger.info(f"Batch embedding {len(adapted_queries)} queries in '{collection_name}'")

        vectors = self.embedding_client.embed_text(
            text=adapted_queries,
            document_type=DocumentTypeEnum.QUERY.value
        )

        if not vectors or len(vectors) == 0:
            logger.warning("Batch embedding returned empty")
            return [{"query": q, "results": []} for q in queries]

        all_results = []
        for query, adapted, vec in zip(queries, adapted_queries, vectors):
            if not vec:
                logger.warning(f"Null vector for query: '{query[:80]}'")
                all_results.append({"query": query, "results": []})
                continue

            docs = await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=vec,
                limit=limit
            )
            docs = docs if docs else []
            logger.debug(f"Batch search for '{query[:50]}...' -> {len(docs)} results")
            all_results.append({"query": query, "results": [d.dict() for d in docs]})

        logger.info(f"Batch search complete | {len(all_results)} queries processed")
        return all_results

    async def search_vector_db_collection(self, project: Project, text: str, 
                                          limit: int = 10,
                                          candidates_n: int = None,
                                          top_k: int = 4,
                                          rerank: str = None,
                                          query_adapter: str = None):

        logger.info(f"search_vector_db_collection | project={project.project_id} | limit={limit} | rerank={rerank} | adapter={query_adapter}")

        has_advanced_params = any([
            candidates_n is not None,
            top_k is not None,
            rerank is not None,
            query_adapter is not None
        ])
        
        if has_advanced_params:
            logger.debug("Using advanced retrieval pipeline")
            return await self._retrieve_and_rerank(
                project=project,
                query=text,
                candidates_n=candidates_n,
                top_k=top_k or limit,
                force_rerank=rerank,
                query_adapter=query_adapter
            )
        
        logger.debug("Using raw vector search (no advanced params)")
        return await self._raw_vector_search(project, text, limit=limit)
    
    # ==================== HELPERS ====================
    
    def _convert_messages_for_provider(self, messages: List) -> List[dict]:
        """Convert LangChain messages to provider-specific format."""
        logger.debug(f"Converting {len(messages)} messages for provider: {type(self.generation_client.enums).__name__}")
        provider_messages = []
        provider_enums = self.generation_client.enums
        
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
            provider_role = role_mapping.get(langchain_role.lower(), provider_enums.USER.value)
            
            if provider_enums == CoHereEnums:
                provider_messages.append({"role": provider_role, "text": content})
            else:
                provider_messages.append({"role": provider_role, "content": content})
        
        logger.debug(f"Converted {len(provider_messages)} messages")
        return provider_messages
    
    # ==================== RAG ANSWER ====================

    async def answer_rag_question(self, project: Project, query: str, 
                                   limit: int = 10,
                                   candidates_n: int = None,
                                   top_k: int = None,
                                   rerank: str = None,
                                   query_adapter: str = None):

        logger.info(f"RAG answer start | project={project.project_id} | query='{query[:80]}'")
        answer, full_prompt, chat_history = None, None, None

        retrieved_documents = await self._retrieve_and_rerank(
            project=project,
            query=query,
            candidates_n=candidates_n,
            top_k=top_k or limit,
            force_rerank=rerank,
            query_adapter=query_adapter
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            logger.warning(f"No documents retrieved for query: '{query[:80]}'")
            return answer, full_prompt, chat_history
        
        logger.info(f"Building RAG prompt with {len(retrieved_documents)} documents")
        context = self.template_parser.format_documents(retrieved_documents)

        prompt_template = self.template_parser.get_chat_prompt("rag", "rag_prompt")
        messages = prompt_template.format_messages(context=context, question=query)
        chat_history = self._convert_messages_for_provider(messages)

        logger.debug("Calling generation client for RAG answer")
        answer = await self.generation_client.generate_text(
            prompt="",
            chat_history=chat_history
        )

        logger.info(f"RAG answer generated | length={len(answer) if answer else 0} chars")
        full_prompt = context

        return answer, full_prompt, chat_history
