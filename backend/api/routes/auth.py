#!/usr/bin/env python3
"""
Authentication API Routes
Simple authentication for local VR training application
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, validator
from services.student_service import StudentService
from services.video_service import VideoService

router = APIRouter()


class LoginRequest(BaseModel):
    name: str
    student_id: str
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name is required')
        return v.strip()
    
    @validator('student_id')
    def validate_student_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Student ID is required')
        return v.strip()


class LoginResponse(BaseModel):
    success: bool
    message: str
    student: Dict[str, Any]
    is_new: bool


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login or register a student
    For local application, this serves as both login and registration
    """
    try:
        # Register/login student
        student_data = await StudentService.register_student(
            request.name, 
            request.student_id
        )
        
        # For existing students, ensure directories are in correct format
        if not student_data['is_new']:
            await StudentService.migrate_student_directories(request.student_id)
        
        # Initialize videos in database if needed
        await VideoService.initialize_videos()
        
        return LoginResponse(
            success=True,
            message=student_data['message'],
            student={
                "id": student_data['id'],
                "name": student_data['name'],
                "student_id": student_data['student_id']
            },
            is_new=student_data['is_new']
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"❌ Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
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
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        return {
            "valid": True,
            "student": student['student'],
            "statistics": student['statistics']
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    except Exception as e:
        print(f"❌ Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed"
        )


@router.post("/logout/{student_id}")
async def logout(student_id: str):
    """
    Logout a student (update last active time)
    """
    try:
        from database.sqlite_db import DatabaseManager
        await DatabaseManager.update_student_activity(student_id)
        
        return {
            "success": True,
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        print(f"❌ Logout error: {e}")
        return {
            "success": True,
            "message": "Logged out"
        }
