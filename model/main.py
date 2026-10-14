"""Crunch3D — local mesh optimization."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router

app = FastAPI(title="Crunch3D API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",") if x.strip()],
    allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "storage": "local"}
