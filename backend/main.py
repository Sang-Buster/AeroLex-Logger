#!/usr/bin/env python3
"""
VR Flight Training Course Backend
FastAPI application for student management, progress tracking, and ASR integration
"""

import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import uvicorn  # noqa: E402

# Import our modules
from api.routes import admin, asr, auth, students, videos  # noqa: E402
from database.sqlite_db import init_database  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402


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
        base_dir / "data" / "ground_truth",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")


# Create FastAPI app
app = FastAPI(
    title="VR Flight Training Course API",
    description="Backend API for VR flight training with ASR evaluation",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

# Static file serving
web_directory = Path(__file__).parent.parent / "web"
if web_directory.exists():
    app.mount(
        "/static", StaticFiles(directory=str(web_directory), html=True), name="static"
    )

# Serve videos with proper byte-range support
videos_directory = Path(__file__).parent.parent / "videos"
if videos_directory.exists():
    from fastapi import HTTPException, Request
    from fastapi.responses import FileResponse, StreamingResponse

    @app.api_route("/videos/{filename}", methods=["GET", "HEAD"])
    async def serve_video(filename: str, request: Request):
        """Serve video files with proper byte-range support for seeking"""
        video_path = videos_directory / filename

        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")

        file_size = video_path.stat().st_size

        # Handle range requests for video seeking
        range_header = request.headers.get("range")

        if range_header:
            # Parse range header
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end = (
                    int(range_match.group(2)) if range_match.group(2) else file_size - 1
                )

                # Ensure end doesn't exceed file size
                end = min(end, file_size - 1)
                content_length = end - start + 1

                def iter_file_range():
                    with open(video_path, "rb") as f:
                        f.seek(start)
                        remaining = content_length
                        while remaining > 0:
                            chunk_size = min(8192, remaining)
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            remaining -= len(chunk)
                            yield chunk

                return StreamingResponse(
                    iter_file_range(),
                    status_code=206,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(content_length),
                        "Content-Type": "video/mp4",
                    },
                )

        # Regular file response for non-range requests
        return FileResponse(
            video_path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"}
        )

    # Keep StaticFiles as fallback
    app.mount(
        "/videos-static",
        StaticFiles(directory=str(videos_directory)),
        name="videos-static",
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VR Flight Training Course API",
        "version": "1.0.0",
        "docs": "/docs",
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
        content={"detail": "Internal server error", "message": str(exc)},
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=["backend"]
    )
