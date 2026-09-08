"""FastAPI application entrypoint for the Signal Clone API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.contacts.router import router as contacts_router
from app.conversations.router import router as conversations_router
from app.database import init_db
from app.messages.router import router as messages_router
from app.settings import cors_origins
from app.websocket.router import router as websocket_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create database tables on startup; no teardown is required."""
    init_db()
    yield


app = FastAPI(
    title="Signal Clone API",
    description="Backend for the Secure Messaging Platform (Signal Clone) assignment.",
    version="0.1.0",
    lifespan=lifespan,
)

# Local Next.js origins always allowed; FRONTEND_ORIGIN adds Vercel in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(contacts_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(websocket_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Signal Clone API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
