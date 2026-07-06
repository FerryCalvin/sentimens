"""
query_expansion.py — LLM-Based Query Expansion via OpenRouter
==============================================================
Converts a raw user keyword into two variants using a language model:
  - a focused Boolean search query (for Twitter/X and web search, which
    understand OR/quotes/grouping)
  - a plain merged-phrase variant with no Boolean operators/quotes (for
    Threads, whose search engine treats those characters literally and
    returns zero results if given the Boolean form)

Both preserve the core topic while adding genuine Indonesian synonyms/slang.

Uses the official `openrouter` Python SDK (pip install openrouter).
Failsafe: any error or timeout falls back to the original keyword for both
variants — the scraper is never blocked.
"""
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a Search Query Optimizer for Indonesian social media sentiment analysis.\n"
    "Given a keyword or phrase, produce TWO search query variants that find relevant posts.\n\n"
    "STEP 1 — Split the keyword into two components:\n"
    "  - EXPANDABLE CORE: the event, action, or topic being discussed (this part gets synonyms)\n"
    "  - MANDATORY ANCHORS: geographic locations, entity names, company tickers, or proper nouns\n"
    "    that MUST appear in every result — do NOT expand or drop these\n\n"
    "STEP 2 — Expand the EXPANDABLE CORE with 3–5 genuine Indonesian synonyms/slang.\n\n"
    "STEP 3 — Produce two output lines:\n"
    "  BOOLEAN: a Twitter/X-style Boolean query — synonyms grouped in parentheses joined by OR,\n"
    "           quoted if multi-word, with MANDATORY ANCHORS placed outside the group (bare terms\n"
    "           are implicitly ANDed). If there are no anchors, output the OR group alone.\n"
    "  PLAIN:   ONE single natural phrase merging the single most common/likely synonym with the\n"
    "           anchors — no quotes, no parentheses, no OR/AND. This must work as plain keyword\n"
    "           input to a simple substring search engine that does not understand Boolean syntax.\n\n"
    "RULES:\n"
    "- Do NOT produce overlapping n-gram pairs from the original phrase.\n"
    "- Do NOT drop or modify mandatory anchors in either line.\n"
    "- Reply with EXACTLY two lines, in this order, no other text:\n"
    "  BOOLEAN: <query>\n"
    "  PLAIN: <phrase>\n\n"
    "EXAMPLES:\n"
    "Input: listrik padam sumatra\n"
    "  → core: \"listrik padam\" | anchors: sumatra\n"
    "  BOOLEAN: (\"listrik padam\" OR \"mati lampu\" OR \"pemadaman listrik\" OR \"byar pet\") sumatra\n"
    "  PLAIN: pemadaman listrik sumatra\n\n"
    "Input: pln pemadaman bergilir\n"
    "  → core: \"pemadaman bergilir\" | anchors: pln\n"
    "  BOOLEAN: (\"pemadaman bergilir\" OR \"mati lampu bergilir\" OR \"byar pet\") pln\n"
    "  PLAIN: pemadaman listrik bergilir pln\n\n"
    "Input: demo mahasiswa jakarta\n"
    "  → core: \"demo mahasiswa\" | anchors: jakarta\n"
    "  BOOLEAN: (\"demo mahasiswa\" OR \"aksi mahasiswa\" OR \"unjuk rasa mahasiswa\") jakarta\n"
    "  PLAIN: aksi mahasiswa jakarta\n\n"
    "Input: BBRI turun saham\n"
    "  → core: turun/saham | anchors: BBRI\n"
    "  BOOLEAN: (BBRI OR \"saham BRI\" OR \"bank BRI\") AND (\"turun\" OR \"anjlok\" OR \"koreksi\")\n"
    "  PLAIN: saham BBRI turun"
)

_startup_logged = False


def log_startup_status() -> None:
    """One-time diagnostic (call at service boot) so a missing API key is immediately obvious."""
    global _startup_logged
    if _startup_logged:
        return
    _startup_logged = True
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "openrouter/auto").strip()
    if api_key:
        logger.info(f"[QueryExpander] OPENROUTER_API_KEY terkonfigurasi (model={model}). Expansion aktif.")
    else:
        logger.warning("[QueryExpander] OPENROUTER_API_KEY TIDAK di-set — expansion di-skip untuk setiap request.")


def _parse_two_lines(text: str, original_keyword: str) -> tuple[str, str] | None:
    boolean_match = re.search(r"BOOLEAN:\s*(.+)", text)
    plain_match   = re.search(r"PLAIN:\s*(.+)", text)
    if not boolean_match or not plain_match:
        return None
    boolean_q = boolean_match.group(1).strip().splitlines()[0].strip()
    plain_q   = plain_match.group(1).strip().splitlines()[0].strip()
    if not boolean_q or not plain_q:
        return None
    return boolean_q, plain_q


def expand_query(original_keyword: str) -> tuple[str, str, str]:
    """
    Expand *original_keyword* into (boolean_query, plain_query, status) via OpenRouter SDK.
    Falls back to *original_keyword* for both variants on any failure/timeout/parse error.

    status: one of expanded / skipped_no_api_key / skipped_empty_response /
            failed_timeout / failed_error / failed_parse
    """
    log_startup_status()

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.warning("[QueryExpander] OPENROUTER_API_KEY not set — using original keyword.")
        return original_keyword, original_keyword, "skipped_no_api_key"

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

    ex = ThreadPoolExecutor(max_workers=1)
    try:
        raw = ex.submit(_call).result(timeout=10)
        ex.shutdown(wait=False)
        if not raw:
            return original_keyword, original_keyword, "skipped_empty_response"
        parsed = _parse_two_lines(raw, original_keyword)
        if parsed is None:
            logger.warning(f"[QueryExpander] Gagal parsing respons LLM ({raw[:120]!r}) — pakai keyword asli.")
            return original_keyword, original_keyword, "failed_parse"
        boolean_q, plain_q = parsed
        logger.info(f"[QueryExpander] '{original_keyword}' → BOOLEAN='{boolean_q}' PLAIN='{plain_q}'")
        return boolean_q, plain_q, "expanded"
    except FutureTimeout:
        ex.shutdown(wait=False)
        logger.warning("[QueryExpander] Timeout (10s) — using original keyword.")
        return original_keyword, original_keyword, "failed_timeout"
    except Exception as e:
        ex.shutdown(wait=False)
        logger.warning(f"[QueryExpander] Fallback to original keyword ({type(e).__name__}: {e})")
        return original_keyword, original_keyword, "failed_error"
