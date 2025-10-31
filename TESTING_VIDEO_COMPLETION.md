# Video Completion Testing Guide

This guide explains how to test the video completion tracking feature without watching entire videos or doing speech ASR.

## 🧪 Testing Methods

### Method 1: Browser Console Testing (Easiest)

1. **Open the web app** and login as a student (e.g., ID: `1234567`)

2. **Open browser console** (Press `F12` or right-click → Inspect → Console tab)

3. **Load the test script:**

   ```javascript
   // Copy and paste the contents of web/assets/js/test_video_completion.js
   // OR if the file is accessible:
   fetch("/static/js/test_video_completion.js")
     .then((r) => r.text())
     .then(eval);
   ```

4. **Run test commands:**

   **Check current progress:**

   ```javascript
   await checkStudentProgress();
   ```

   **Simulate a single video completion:**

   ```javascript
   // Simulate video 0 with 95% watched and 85% similarity
   await testVideoCompletion(0, 95, 85);
   ```

   **View all videos breakdown:**

   ```javascript
   await getVideoBreakdown();
   ```

   **Test multiple videos at once:**

   ```javascript
   await testMultipleCompletions(3); // Tests 3 videos
   ```

   **Simulate currently open video:**

   ```javascript
   // First, open a video in the UI
   // Then run:
   simulateVideoCompletion();
   ```

### Method 2: Python Test Script

1. **Install requirements:**

   ```bash
   pip install requests
   ```

2. **Test single video completion:**

   ```bash
   python test_video_completion.py 1234567 --video 0 --watch 95 --similarity 85
   ```

3. **Check student progress only:**

   ```bash
   python test_video_completion.py 1234567 --check
   ```

4. **Test multiple videos:**
   ```bash
   python test_video_completion.py 1234567 --multiple 3
   ```

### Method 3: Direct API Testing (curl)

**Send completion data directly:**

```bash
curl -X POST http://150.136.241.0:5000/uploadVideoResults \
  -H "Content-Type: application/json" \
  -d '{
    "id": "1234567",
    "videoNumber": 0,
    "status": "1",
    "similarity": "85.50",
    "watchPercentage": "95.00"
  }'
```

**Check student progress:**

```bash
curl http://localhost:8000/api/v1/students/1234567/dashboard
curl http://localhost:8000/api/v1/students/1234567/statistics
curl http://localhost:8000/api/v1/students/1234567/progress
```

## 📊 What to Check

### 1. External Server Logs

- Check if the external server at `http://150.136.241.0:5000` received the POST request
- Verify the payload contains correct data:
  - `id`: Student ID
  - `videoNumber`: Video index
  - `status`: "1" for completed
  - `similarity`: Average similarity percentage
  - `watchPercentage`: Watch time percentage

### 2. Local Database

Check the SQLite database for student progress:

```bash
sqlite3 backend/database/database.db

-- View all students
SELECT * FROM students;

-- View video progress
SELECT * FROM student_video_progress WHERE student_id = '1234567';

-- View ASR results
SELECT * FROM asr_results WHERE student_id = '1234567';
```

### 3. Console Output

In the browser console, you should see:

```
📊 Video Completion Check:
  - Video: 7L Departure North
  - Watch time: 1248s / 1308s (95.4%)
  - Average similarity: 87.3% (12 scores)
  - Required watch: 90%
  - Required similarity: 50%
✅ Video completion criteria met! Reporting to server...
📤 Sending completion data to server: {...}
✅ Server response: {...}
```

## 🔍 Verification Checklist

- [ ] Browser console shows completion check logs
- [ ] POST request sent to external server (check network tab)
- [ ] External server responds with success
- [ ] Local database updated with video progress
- [ ] Student statistics show correct totals
- [ ] Video shows as completed in UI after refresh

## ⚙️ Configuration

Edit `asr_config.ini` to change thresholds:

```ini
[SESSION_SETTINGS]
MIN_SIMILARITY_PERCENTAGE = 50   # Minimum average similarity (0-100%)
MIN_VIDEO_WATCH_PERCENTAGE = 90  # Minimum watch time (0-100%)
```

## 🐛 Troubleshooting

**Problem: No POST request sent**

- Check browser console for errors
- Verify video was opened and has duration
- Check that `sessionSimilarityScores` has data

**Problem: External server not responding**

- Verify server is running at `http://150.136.241.0:5000`
- Check network connectivity
- Look for CORS errors in console

**Problem: Criteria not met**

- Lower thresholds in config file
- Use test functions to inject fake data
- Check console logs for actual percentages

## 📝 Example Test Session

```javascript
// 1. Login as student
// 2. In console:

// Check current state
await checkStudentProgress();

// Simulate completing video 0
await testVideoCompletion(0, 95, 85);

// Check updated state
await checkStudentProgress();

// View breakdown
await getVideoBreakdown();

// Test multiple videos
await testMultipleCompletions(5);
```

## 🎯 Success Indicators

✅ Console log shows: `✅ Video completion criteria met!`
✅ Console log shows: `✅ Server response: {...}`
✅ Network tab shows POST to `http://150.136.241.0:5000/uploadVideoResults`
✅ Response status is 200 OK
✅ `checkStudentProgress()` shows updated data
