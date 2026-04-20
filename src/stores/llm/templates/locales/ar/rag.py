from langchain_core.prompts import ChatPromptTemplate

#### RAG PROMPTS ####

#### System Message ####
system_message = "\n".join([
    "أنت مساعد يجيب على الأسئلة بناءً فقط على المستندات المقدمة.",
    "",
    "تعليمات مهمة:",
    "- أجب فقط باستخدام المعلومات الموجودة في المستندات أدناه",
    "- إذا لم تحتوي المستندات على الإجابة، قل \"لا أستطيع العثور على هذه المعلومات في المستندات المقدمة\"",
    "- لا تقم بتأليف أو استنتاج معلومات غير موجودة صراحة في المستندات",
    "- أجب بنفس لغة سؤال المستخدم",
    "- كن موجزاً ودقيقاً"
])

#### Document Formatting Function ####
def format_document(doc_num: int, chunk_text: str) -> str:
    """Format a single document for context injection (Arabic).
    
    Args:
        doc_num: Document index (1-based)
        chunk_text: Document content
        
    Returns:
        Formatted document string in Arabic
    """
    return f"## المستند رقم: {doc_num}\n### المحتوى: {chunk_text}"

#### RAG Prompt Template ####
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    ("human", "{context}\n\nبناءً فقط على المستندات المذكورة أعلاه، يرجى الإجابة على السؤال التالي:\n\n{question}")
])
