from langchain_core.prompts import ChatPromptTemplate

#### QUERY REWRITE PROMPTS ####

rewrite_system = "\n".join([
    "أنت محسّن استعلامات البحث.",
    "أعد صياغة سؤال المستخدم ليكون أكثر فعالية للبحث الدلالي.",
    "اجعله أكثر تحديداً، أضف مرادفات ذات صلة، ووسّع الاختصارات.",
    "أعد فقط الاستعلام المُعاد صياغته، لا شيء آخر."
])

rewrite_user = "الاستعلام الأصلي: {query}\n\nالاستعلام المُعاد صياغته:"

rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", rewrite_system),
    ("human", rewrite_user)
])

#### HYDE (Hypothetical Document Embeddings) PROMPTS ####

hyde_system = "\n".join([
    "أنت مساعد خبير.",
    "بالنظر إلى سؤال، اكتب فقرة قصيرة تمثل الإجابة المثالية.",
    "ستُستخدم هذه الفقرة للعثور على مستندات مشابهة.",
    "اكتب كأنك تجيب من قاعدة معرفية.",
    "كن واقعياً ومفيداً. لا تقل 'أعتقد' أو 'أظن'.",
    "أعد فقط فقرة الإجابة الافتراضية، لا شيء آخر."
])

hyde_user = "السؤال: {query}\n\nالإجابة الافتراضية:"

hyde_prompt = ChatPromptTemplate.from_messages([
    ("system", hyde_system),
    ("human", hyde_user)
])