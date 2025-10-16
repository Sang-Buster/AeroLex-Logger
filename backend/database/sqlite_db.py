#!/usr/bin/env python3
"""
SQLite Database Setup and Models
Simple database for local VR training application
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "vr_training.db"


async def init_database():
    """Initialize the SQLite database with required tables"""

    # Ensure database directory exists
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Students table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                student_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_videos INTEGER DEFAULT 0,
                completed_videos INTEGER DEFAULT 0
            )
        """)

        # Student sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS student_sessions (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                duration INTEGER,  -- in seconds
                status TEXT DEFAULT 'started',  -- started, completed, failed
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
        """)

        # ASR results table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS asr_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                transcript TEXT,
                ground_truth TEXT,
                confidence REAL,
                wer REAL,  -- Word Error Rate
                cer REAL,  -- Character Error Rate
                similarity_score REAL,
                audio_file_path TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES student_sessions (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
        """)

        # Video progress table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS video_progress (
                student_id TEXT,
                video_id TEXT,
                unlocked BOOLEAN DEFAULT FALSE,
                completed BOOLEAN DEFAULT FALSE,
                best_score REAL DEFAULT 0.0,
                attempts INTEGER DEFAULT 0,
                last_attempt TIMESTAMP,
                PRIMARY KEY (student_id, video_id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
        """)

        # Videos metadata table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                description TEXT,
                duration INTEGER,  -- in seconds
                order_index INTEGER NOT NULL,
                ground_truth_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
        print("✅ Database initialized successfully")


class DatabaseManager:
    """Database manager for VR training application"""

    @staticmethod
    async def get_connection():
        """Get database connection"""
        return aiosqlite.connect(DATABASE_PATH)

    # Student operations
    @staticmethod
    async def create_student(student_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new student"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO students (id, name, student_id)
                    VALUES (?, ?, ?)
                """,
                    (
                        student_data["id"],
                        student_data["name"],
                        student_data["student_id"],
                    ),
                )

                # Unlock the first video for new students
                await db.execute(
                    """
                    INSERT OR IGNORE INTO video_progress (student_id, video_id, unlocked, completed, best_score, attempts)
                    SELECT ?, id, 1, 0, 0.0, 0 FROM videos WHERE order_index = 1
                """,
                    (student_data["student_id"],),
                )

                await db.commit()
                return student_data
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed" in str(e):
                    raise ValueError("Student ID already exists")
                raise e

    @staticmethod
    async def get_student(student_id: str) -> Optional[Dict[str, Any]]:
        """Get student by student_id"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def update_student_activity(student_id: str):
        """Update student's last active timestamp"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                UPDATE students 
                SET last_active = CURRENT_TIMESTAMP 
                WHERE student_id = ?
            """,
                (student_id,),
            )
            await db.commit()

    # Video operations
    @staticmethod
    async def get_videos() -> List[Dict[str, Any]]:
        """Get all videos ordered by order_index"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM videos ORDER BY order_index"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @staticmethod
    async def get_student_video_progress(student_id: str) -> List[Dict[str, Any]]:
        """Get video progress for a student"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT v.*, vp.unlocked, vp.completed, vp.best_score, vp.attempts, vp.last_attempt
                FROM videos v
                LEFT JOIN video_progress vp ON v.id = vp.video_id AND vp.student_id = ?
                ORDER BY v.order_index
            """,
                (student_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @staticmethod
    async def unlock_next_video(student_id: str, current_video_id: str):
        """Unlock the next video after completing current one"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Get current video order
            async with db.execute(
                """
                SELECT order_index FROM videos WHERE id = ?
            """,
                (current_video_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return

                current_order = row[0]
                next_order = current_order + 1

                # Unlock next video
                await db.execute(
                    """
                    INSERT OR REPLACE INTO video_progress (student_id, video_id, unlocked)
                    SELECT ?, id, TRUE FROM videos WHERE order_index = ?
                """,
                    (student_id, next_order),
                )

                await db.commit()

    # Session operations
    @staticmethod
    async def create_session(session_data: Dict[str, Any]) -> str:
        """Create a new student session"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                INSERT INTO student_sessions (id, student_id, video_id, status)
                VALUES (?, ?, ?, ?)
            """,
                (
                    session_data["id"],
                    session_data["student_id"],
                    session_data["video_id"],
                    session_data.get("status", "started"),
                ),
            )
            await db.commit()
            return session_data["id"]

    @staticmethod
    async def complete_session(session_id: str, duration: int):
        """Mark session as completed"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                UPDATE student_sessions 
                SET completed_at = CURRENT_TIMESTAMP, duration = ?, status = 'completed'
                WHERE id = ?
            """,
                (duration, session_id),
            )
            await db.commit()

    # ASR results operations
    @staticmethod
    async def save_asr_result(asr_data: Dict[str, Any]) -> int:
        """Save ASR transcription and evaluation result"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                """
                INSERT INTO asr_results (
                    session_id, student_id, video_id, transcript, ground_truth,
                    confidence, wer, cer, similarity_score, audio_file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    asr_data["session_id"],
                    asr_data["student_id"],
                    asr_data["video_id"],
                    asr_data["transcript"],
                    asr_data.get("ground_truth", ""),
                    asr_data.get("confidence", 0.0),
                    asr_data.get("wer", 1.0),
                    asr_data.get("cer", 1.0),
                    asr_data.get("similarity_score", 0.0),
                    asr_data.get("audio_file_path", ""),
                ),
            )
            asr_id = cursor.lastrowid
            await db.commit()
            return asr_id

    @staticmethod
    async def get_student_asr_results(
        student_id: str, video_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get ASR results for a student, optionally filtered by video"""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row

            query = "SELECT * FROM asr_results WHERE student_id = ?"
            params = [student_id]

            if video_id:
                query += " AND video_id = ?"
                params.append(video_id)

            query += " ORDER BY timestamp DESC"

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
