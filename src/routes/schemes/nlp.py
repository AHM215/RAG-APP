from pydantic import BaseModel
from typing import List, Optional, Literal

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 10
    candidates_n: Optional[int] = None
    top_k: Optional[int] = None
    rerank: Optional[Literal["none", "cross_encoder", "llm"]] = None
    query_adapter: Optional[Literal["none", "rewrite", "hyde"]] = None
