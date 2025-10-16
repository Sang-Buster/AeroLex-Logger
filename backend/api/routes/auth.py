#!/usr/bin/env python3
"""
Authentication API Routes
Simple authentication for local VR training application
"""

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, validator
from services.student_service import StudentService
from services.video_service import VideoService

# Load environment variables from .env file
load_dotenv()

router = APIRouter()

# Read from env
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD is not set in .env file")


class LoginRequest(BaseModel):
    name: str
    student_id: str
    password: Optional[str] = None

    @validator("name")
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name is required")
        return v.strip()

    @validator("student_id")
    def validate_student_id(cls, v):
        if not v or not v.strip():
            raise ValueError("Student ID is required")
        return v.strip()


class LoginResponse(BaseModel):
    success: bool
    message: str
    student: Dict[str, Any]
    is_new: bool
    is_admin: bool = False


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login or register a student / admin
    For local application, this serves as both login and registration for students
    Admin login requires special password
    """
    try:
        # Check if this is an admin login attempt
        if request.student_id.lower() == "admin":
            # Admin login requires password
            if not request.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin password is required",
                )

            # Validate admin credentials
            if request.password == ADMIN_PASSWORD:
                return LoginResponse(
                    success=True,
                    message="Admin login successful",
                    student={
                        "id": "admin",
                        "name": request.name,
                        "student_id": "admin",
                    },
                    is_new=False,
                    is_admin=True,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid admin credentials",
                )

        # Regular student login/registration (non-admin)
        student_data = await StudentService.register_student(
            request.name, request.student_id
        )

        # For existing students, ensure directories are in correct format
        if not student_data["is_new"]:
            await StudentService.migrate_student_directories(request.student_id)

        # Initialize videos in database if needed
        await VideoService.initialize_videos()

        return LoginResponse(
            success=True,
            message=student_data["message"],
            student={
                "id": student_data["id"],
                "name": student_data["name"],
                "student_id": student_data["student_id"],
            },
            is_new=student_data["is_new"],
            is_admin=False,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"❌ Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.get("/validate/{student_id}")
async def validate_student(student_id: str):
    """
    Validate if a student exists and is active
    """
    try:
        # Get student data
        student = await StudentService.get_student_progress(student_id)

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
            )

        return {
            "valid": True,
            "student": student["student"],
            "statistics": student["statistics"],
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )
    except Exception as e:
        print(f"❌ Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed",
        )


@router.post("/logout/{student_id}")
async def logout(student_id: str):
    """
    Logout a student (don't update timestamp so they don't appear as active)
    """
    try:
        # Don't update last_active on logout to avoid showing as "active"
        # The timestamp will represent their last actual activity, not logout time
        print(f"👋 Student {student_id} logged out")

        return {"success": True, "message": "Logged out successfully"}

    except Exception as e:
        print(f"❌ Logout error: {e}")
        return {"success": True, "message": "Logged out"}
