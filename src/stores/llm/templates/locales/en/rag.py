from langchain_core.prompts import ChatPromptTemplate

#### RAG PROMPTS ####

#### System Message ####
system_message = "\n".join([
    "You are an assistant that answers questions based ONLY on the provided documents.",
    "",
    "CRITICAL INSTRUCTIONS:",
    "- Answer ONLY using information from the documents below",
    "- If the documents do not contain the answer, say \"I cannot find this information in the provided documents\"",
    "- Do NOT make up or infer information not explicitly stated in the documents",
    "- Respond in the same language as the user's query",
    "- Be concise and precise"
])

#### Document Formatting Function ####
def format_document(doc_num: int, chunk_text: str) -> str:
    """Format a single document for context injection.
    
    Args:
        doc_num: Document index (1-based)
        chunk_text: Document content
        
    Returns:
        Formatted document string
    """
    return f"## Document No: {doc_num}\n### Content: {chunk_text}"

#### RAG Prompt Template ####
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    ("human", "{context}\n\nBased only on the above documents, please answer the following question:\n\n{question}")
])
