"""
query_expansion.py — LLM-Based Query Expansion via OpenRouter
==============================================================
Converts a raw user keyword into a focused Boolean search query
using a language model, preserving the core topic while adding
genuine Indonesian synonyms and slang.

Uses the official `openrouter` Python SDK (pip install openrouter).
Failsafe: any error or timeout silently falls back to the original
keyword — the scraper is never blocked.
"""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dotenv import load_dotenv

load_dotenv()

_SYSTEM_PROMPT = (
    "You are a Search Query Optimizer for Indonesian social media sentiment analysis on Twitter/X.\n"
    "Given a keyword or phrase, produce a focused Boolean search query that finds relevant tweets.\n\n"
    "STEP 1 — Split the keyword into two components:\n"
    "  - EXPANDABLE CORE: the event, action, or topic being discussed (this part gets synonyms)\n"
    "  - MANDATORY ANCHORS: geographic locations, entity names, company tickers, or proper nouns\n"
    "    that MUST appear in every result — do NOT expand or drop these\n\n"
    "STEP 2 — Expand the EXPANDABLE CORE with 3–5 genuine Indonesian synonyms/slang using OR, "
    "grouped in parentheses.\n\n"
    "STEP 3 — Place MANDATORY ANCHORS outside the parentheses group "
    "(Twitter implicitly ANDs bare terms).\n\n"
    "OUTPUT FORMAT: (synonym1 OR \"synonym2\" OR ...) ANCHOR1 ANCHOR2\n"
    "If there are no mandatory anchors, output the OR group without parentheses.\n\n"
    "RULES:\n"
    "- Do NOT produce overlapping n-gram pairs from the original phrase.\n"
    "- Do NOT drop or modify mandatory anchors.\n"
    "- Reply ONLY with the Boolean query string. No explanation, no surrounding quotes.\n\n"
    "EXAMPLES:\n"
    "Input: listrik padam sumatra\n"
    "  → core: \"listrik padam\" | anchors: sumatra\n"
    "  Good: (\"listrik padam\" OR \"mati lampu\" OR \"pemadaman listrik\" OR \"byar pet\") sumatra\n"
    "  Bad:  \"listrik padam\" OR \"mati lampu\" OR \"pemadaman listrik\"  ← dropped sumatra\n\n"
    "Input: demo mahasiswa jakarta\n"
    "  → core: \"demo mahasiswa\" | anchors: jakarta\n"
    "  Good: (\"demo mahasiswa\" OR \"aksi mahasiswa\" OR \"unjuk rasa mahasiswa\") jakarta\n\n"
    "Input: BBRI turun saham\n"
    "  → core: turun/saham | anchors: BBRI\n"
    "  Good: (BBRI OR \"saham BRI\" OR \"bank BRI\") AND (\"turun\" OR \"anjlok\" OR \"koreksi\")"
)


def expand_query(original_keyword: str) -> str:
    """
    Expand *original_keyword* into a Boolean search query via OpenRouter SDK.
    Returns *original_keyword* unchanged on any failure or timeout.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("[QueryExpander] OPENROUTER_API_KEY not set — using original keyword.")
        return original_keyword

    model = os.getenv("OPENROUTER_MODEL", "openrouter/auto").strip()

    def _call() -> str:
        from openrouter import OpenRouter
        with OpenRouter(api_key=api_key) as client:
            resp = client.chat.send(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": original_keyword},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            expanded = ex.submit(_call).result(timeout=3)
        if expanded:
            print(f"[QueryExpander] '{original_keyword}' → '{expanded}'")
            return expanded
        return original_keyword
    except FutureTimeout:
        print("[QueryExpander] Timeout (3s) — using original keyword.")
        return original_keyword
    except Exception as e:
        print(f"[QueryExpander] Fallback to original keyword ({type(e).__name__}: {e})")
        return original_keyword
