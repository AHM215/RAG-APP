from langchain_core.prompts import ChatPromptTemplate

#### QUERY REWRITE PROMPTS ####

rewrite_system = "\n".join([
    "You are a search query optimizer.",
    "Rewrite the user's question to be more effective for semantic search.",
    "Make it more specific, add relevant synonyms, and expand abbreviations.",
    "Return ONLY the rewritten query, nothing else."
])

rewrite_user = "Original query: {query}\n\nRewritten query:"

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", rewrite_system),
    ("human", rewrite_user)
])

#### HYDE (Hypothetical Document Embeddings) PROMPTS ####

hyde_system = "\n".join([
    "You are an expert assistant.",
    "Given a question, write a short paragraph that would be the ideal answer.",
    "This paragraph will be used to find similar documents.",
    "Write as if you are answering from a knowledge base.",
    "Be factual and informative. Do not say 'I think' or 'I believe'.",
    "Return ONLY the hypothetical answer paragraph, nothing else."
])

hyde_user = "Question: {query}\n\nHypothetical answer:"

hyde_prompt = ChatPromptTemplate.from_messages([
    ("system", hyde_system),
    ("human", hyde_user)
])