from pydantic import BaseModel
from typing import List, Optional

class ScrapeRequest(BaseModel):
    keyword: str
    limit: int = 50
    sources: List[str] = ["twitter", "news"]

class ScrapedItem(BaseModel):
    id: str
    source: str
    raw_text: str
    date: str
    url: Optional[str] = None
