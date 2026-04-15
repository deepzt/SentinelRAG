from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, documents, query
from app.core.config import settings

app = FastAPI(
    title="SentinelRAG",
    description="Enterprise RBAC-aware RAG assistant",
    version="0.1.0",
    # Swagger UI available in development only — never expose in production
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit frontend only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "sentinelrag-backend"}
