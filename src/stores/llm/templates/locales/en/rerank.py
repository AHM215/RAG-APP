from langchain_core.prompts import ChatPromptTemplate

#### RERANK PROMPTS ####

system_message = "\n".join([
    "You are a relevance ranking assistant.",
    "Given a query and a numbered list of passages,",
    "return ONLY a JSON array of passage indices (0-based)",
    "sorted from most to least relevant to the query.",
    "Do not include explanations."
])

user_template = "\n".join([
    "Query: {query}",
    "",
    "Passages:",
    "{passages}",
    "",
    "Return a JSON array of indices, e.g. [2, 0, 4, 1, 3]."
])

rerank_prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    ("human", user_template)
])