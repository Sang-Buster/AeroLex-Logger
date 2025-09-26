#!/usr/bin/env python3
"""
VR Flight Training Course Backend
FastAPI application for student management, progress tracking, and ASR integration
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import uvicorn  #noqa: E402

# Import our modules
from api.routes import asr, auth, students, videos  #noqa: E402
from database.sqlite_db import init_database  #noqa: E402
from fastapi import FastAPI  #noqa: E402
from fastapi.middleware.cors import CORSMiddleware  #noqa: E402
from fastapi.responses import JSONResponse  #noqa: E402
from fastapi.staticfiles import StaticFiles  #noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("🚀 Starting VR Flight Training Backend...")
    
    # Initialize database
    await init_database()
    
    # Create necessary directories
    create_directories()
    
    print("✅ Backend startup complete!")
    yield
    
    # Shutdown
    print("🛑 Shutting down VR Flight Training Backend...")


def create_directories():
    """Create necessary directories for the application"""
    base_dir = Path(__file__).parent.parent
    
    directories = [
        base_dir / "audios",
        base_dir / "logs" / "students",
        base_dir / "backend" / "static" / "students",
        base_dir / "data" / "ground_truth"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")


# Create FastAPI app
app = FastAPI(
    title="VR Flight Training Course API",
    description="Backend API for VR flight training with ASR evaluation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(students.router, prefix="/api/v1/students", tags=["Students"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["Videos"])
app.include_router(asr.router, prefix="/api/v1/asr", tags=["ASR"])

# Static file serving
web_directory = Path(__file__).parent.parent / "web"
if web_directory.exists():
    app.mount("/static", StaticFiles(directory=str(web_directory), html=True), name="static")

# Serve videos
videos_directory = Path(__file__).parent.parent / "videos"
if videos_directory.exists():
    app.mount("/videos", StaticFiles(directory=str(videos_directory)), name="videos")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VR Flight Training Course API", 
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "VR Flight Training Backend is running"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    print(f"❌ Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["backend"]
    )
