import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.routes import datasets, charts, generate, outputs, collections

app = FastAPI(
    title="AccessViz API",
    description="Semantic chart description benchmark — dataset browsing and LLM generation",
    version="0.1.0",
)

allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", settings.allowed_origins).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve local chart images at /static/<source>/images/<filename>.png
app.mount("/static", StaticFiles(directory=str(settings.datasets_dir)), name="static")

app.include_router(datasets.router)
app.include_router(charts.router)
app.include_router(generate.router)
app.include_router(outputs.router)
app.include_router(collections.router)


@app.get("/health")
def health():
    return {"status": "ok"}
