#!/usr/bin/env python3
"""
Quick test script to verify database schema and functionality
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from database.sqlite_db import DatabaseManager


async def test_database():
    """Test database setup and queries"""
    print("🧪 Testing Database Setup\n")

    # Test 1: Check tables exist
    print("1️⃣ Checking database tables...")
    async with await DatabaseManager.get_connection() as db:
        async with db.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """
        ) as cursor:
            tables = await cursor.fetchall()
            table_names = [t[0] for t in tables]
            print(f"   Found {len(table_names)} tables: {', '.join(table_names)}")

            required_tables = [
                "students",
                "videos",
                "video_progress",
                "student_sessions",
                "asr_results",
            ]
            for table in required_tables:
                if table in table_names:
                    print(f"   ✅ {table} exists")
                else:
                    print(f"   ❌ {table} MISSING!")

    # Test 2: Check video_progress schema
    print("\n2️⃣ Checking video_progress schema...")
    async with await DatabaseManager.get_connection() as db:
        async with db.execute("PRAGMA table_info(video_progress)") as cursor:
            columns = await cursor.fetchall()
            col_names = [c[1] for c in columns]
            print(f"   Columns: {', '.join(col_names)}")

            required_cols = [
                "student_id",
                "video_id",
                "unlocked",
                "completed",
                "best_score",
                "attempts",
                "last_attempt",
            ]
            for col in required_cols:
                if col in col_names:
                    print(f"   ✅ {col} exists")
                else:
                    print(f"   ❌ {col} MISSING!")

    # Test 3: Check student_sessions schema
    print("\n3️⃣ Checking student_sessions schema...")
    async with await DatabaseManager.get_connection() as db:
        async with db.execute("PRAGMA table_info(student_sessions)") as cursor:
            columns = await cursor.fetchall()
            col_names = [c[1] for c in columns]
            print(f"   Columns: {', '.join(col_names)}")

            if "duration" in col_names:
                print("   ✅ duration column exists for time tracking")
            else:
                print("   ❌ duration column MISSING!")

    # Test 4: Test video progress query with time
    print("\n4️⃣ Testing video progress query with time tracking...")
    try:
        test_student = "sang_123"  # Use your test student ID
        async with await DatabaseManager.get_connection() as db:
            db.row_factory = db.Row
            async with db.execute(
                """
                SELECT v.id, 
                       v.title,
                       vp.unlocked, 
                       vp.completed, 
                       vp.best_score, 
                       vp.attempts,
                       COALESCE(SUM(ss.duration), 0) as time_spent_seconds
                FROM videos v
                LEFT JOIN video_progress vp ON v.id = vp.video_id AND vp.student_id = ?
                LEFT JOIN student_sessions ss ON v.id = ss.video_id 
                                               AND ss.student_id = ? 
                                               AND ss.status = 'completed' 
                                               AND ss.duration IS NOT NULL
                GROUP BY v.id
                ORDER BY v.order_index
                LIMIT 3
            """,
                (test_student, test_student),
            ) as cursor:
                videos = await cursor.fetchall()
                if videos:
                    print(f"   ✅ Query successful, found {len(videos)} videos")
                    for video in videos:
                        v_dict = dict(video)
                        print(
                            f"   📹 {v_dict['title']}: "
                            f"attempts={v_dict.get('attempts', 0)}, "
                            f"time={v_dict.get('time_spent_seconds', 0)}s, "
                            f"unlocked={v_dict.get('unlocked')}"
                        )
                else:
                    print(f"   ⚠️ No videos found for student {test_student}")
    except Exception as e:
        print(f"   ❌ Query failed: {e}")

    # Test 5: Check first video is unlocked for test student
    print("\n5️⃣ Checking first video unlock status...")
    try:
        test_student = "sang_123"
        async with await DatabaseManager.get_connection() as db:
            async with db.execute(
                """
                SELECT v.order_index, v.title, vp.unlocked
                FROM videos v
                LEFT JOIN video_progress vp ON v.id = vp.video_id AND vp.student_id = ?
                WHERE v.order_index = 1
            """,
                (test_student,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    unlocked = row[2]
                    if unlocked:
                        print(f"   ✅ First video '{row[1]}' is unlocked")
                    else:
                        print(
                            f"   ⚠️ First video '{row[1]}' is LOCKED (should be unlocked)"
                        )
                else:
                    print("   ⚠️ First video not found or no progress entry")
    except Exception as e:
        print(f"   ❌ Check failed: {e}")

    print("\n✅ Database tests complete!\n")


if __name__ == "__main__":
    asyncio.run(test_database())
