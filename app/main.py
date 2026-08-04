"""Sourcely API application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import auth, products, projects, proposals

app = FastAPI(
    title="Sourcely API",
    description="Entry-tier CRM for solo interior designers",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(products.router)
app.include_router(proposals.router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
