import os
from pydantic import BaseModel
from typing import List, Optional

class ScrapeRequest(BaseModel):
    keyword: str
    limit: int = int(os.getenv("SCRAPE_LIMIT", "200"))
    sources: List[str] = ["twitter", "web"]  # "web" menggantikan "news"
    days_back: int = int(os.getenv("DAYS_BACK", "7"))

class ScrapedItem(BaseModel):
    id: str
    source: str
    raw_text: str
    date: str
    url: Optional[str] = None
