# ============================================================
# scraper/main.py — FastAPI Scraper Microservice (Port 8000)
# Mengimplementasikan FR-SC-01, FR-SC-02, FR-SC-03
# ============================================================
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from scraper import run_scrape

# ---- Logging ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---- Pydantic Models (FR-SC-01) ----
class ScrapeRequest(BaseModel):
    """Request model untuk endpoint POST /scrape."""
    keyword: str = Field(..., min_length=1, max_length=200, description="Kata kunci pencarian")
    limit: int = Field(default=100, ge=10, le=500, description="Jumlah data yang diminta")

    @validator("keyword")
    def keyword_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Kata kunci tidak boleh hanya spasi")
        return v.strip()


class TweetItem(BaseModel):
    """Model untuk satu item hasil scraping."""
    text: str
    date: str


class ScrapeResponse(BaseModel):
    """Response model untuk endpoint POST /scrape (FR-SC-02)."""
    status: str
    count: int
    data: list[TweetItem]
    message: str = ""


# ---- FastAPI App ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager untuk startup/shutdown."""
    logger.info("FastAPI Scraper Service dimulai — Port 8000")
    yield
    logger.info("FastAPI Scraper Service dihentikan")


app = FastAPI(
    title="SentimenID Scraper Service",
    description="Microservice untuk scraping konten dari platform media sosial dan web.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — Hanya izinkan dari localhost Flask (NFR-S-04)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ============================================================
# ENDPOINT: POST /scrape (FR-SC-01, FR-SC-02, FR-SC-03)
# ============================================================

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_endpoint(request: ScrapeRequest):
    """
    FR-SC-01: Endpoint scraping utama.
    
    Menerima kata kunci dan limit, kemudian menjalankan scraping
    secara asinkronus menggunakan Playwright.
    
    Returns:
        ScrapeResponse dengan data tweet dan status
    """
    logger.info(f"Menerima permintaan scraping: keyword='{request.keyword}', limit={request.limit}")
    
    try:
        # FR-SC-03: Jalankan scraping secara asinkronus
        result = await run_scrape(
            keyword=request.keyword,
            limit=request.limit,
        )
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=503,
                detail=result.get("message", "Layanan scraping tidak tersedia"),
            )
        
        # Konversi ke response model
        data_items = [
            TweetItem(
                text=item.get("text", ""),
                date=item.get("date", ""),
            )
            for item in result["data"]
            if item.get("text", "").strip()
        ]
        
        logger.info(f"Scraping selesai: {len(data_items)} item berhasil")
        
        return ScrapeResponse(
            status="success",
            count=len(data_items),
            data=data_items,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tidak terduga pada endpoint /scrape: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan internal pada layanan scraping.",
        )


# ============================================================
# ENDPOINT: GET /health
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint untuk verifikasi layanan aktif."""
    return {
        "status": "ok",
        "service": "FastAPI Scraper Service",
        "port": 8000,
        "message": "Layanan scraping aktif dan siap menerima permintaan",
    }


@app.get("/")
async def root():
    """Root endpoint — redirect ke dokumentasi API."""
    return {
        "service": "SentimenID Scraper Microservice",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "POST /scrape": "Endpoint utama untuk scraping konten",
        }
    }


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # NFR-S-04: Hanya localhost
        port=8000,
        reload=False,
        workers=1,
        log_level="info",
    )
