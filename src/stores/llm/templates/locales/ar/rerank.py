from langchain_core.prompts import ChatPromptTemplate

#### RERANK PROMPTS ####

system_message = "\n".join([
    "أنت مساعد لترتيب النتائج حسب الصلة.",
    "بالنظر إلى استعلام وقائمة مرقمة من النصوص،",
    "أعد فقط مصفوفة JSON تحتوي على فهارس النصوص (تبدأ من 0)",
    "مرتبة من الأكثر صلة إلى الأقل صلة بالاستعلام.",
    "لا تضف أي شرح."
])

user_template = "\n".join([
    "الاستعلام: {query}",
    "",
    "النصوص:",
    "{passages}",
    "",
    "أعد مصفوفة JSON من الفهارس، مثال: [2, 0, 4, 1, 3]."
])

rerank_prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    ("human", user_template)
])