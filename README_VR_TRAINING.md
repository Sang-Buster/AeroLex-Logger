# VR Flight Training Course System

A comprehensive VR flight training platform with real-time speech recognition, automatic evaluation, and student progress tracking.

## 🎯 Overview

This system combines:

- **VR Video Training**: Progressive video unlocking system
- **Real-time ASR**: Speech recognition during video playback
- **Automatic Evaluation**: Compare student speech to ground truth
- **Progress Tracking**: Individual student analytics and scoring
- **Student Management**: Login system with persistent progress

## 🏗️ Architecture

```
Frontend (HTML/JS/Tailwind)
    ↓
FastAPI Backend
    ↓
SQLite Database + ASR Service
    ↓
Student-Specific Directories
```

### Components

1. **Web Interface** (`web/`)

   - Login page with student authentication
   - Dashboard with progress overview
   - Video player with VR integration
   - Live transcription display
   - Real-time evaluation results

2. **Backend API** (`backend/`)

   - FastAPI server with REST endpoints
   - SQLite database for student data
   - Session management
   - Progress tracking
   - ASR integration

3. **Enhanced ASR Service** (`src/asr_service_vr.py`)

   - Student-specific audio/log directories
   - Session-aware transcription
   - Backend integration for evaluation
   - Real-time ground truth comparison

4. **Student Data Structure**
   ```
   audios/
   ├── studentName_studentId/
   │   ├── speech_2025-09-25T10-30-45_123456.wav
   │   └── speech_2025-09-25T10-31-12_789012.wav
   logs/
   └── students/
       └── studentName_studentId/
           ├── asr_results.jsonl
           ├── asr.out
           └── asr.err
   ```

## 🚀 Quick Start

### 1. Install Backend Dependencies

```bash
# Install backend requirements
cd backend
pip install -r requirements.txt
```

### 2. Start the Backend Server

```bash
# From project root
python src/start_backend.py
```

The backend will be available at:

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:8000/static/

### 3. Open the Web Interface

Navigate to `http://localhost:8000/static/` in your browser and:

1. **Login**: Enter student name and ID
2. **View Dashboard**: See progress and available videos
3. **Watch Videos**: Click unlocked videos to start training
4. **Record Speech**: Use microphone during video playback
5. **View Results**: Get real-time evaluation scores

### 4. (Optional) Start Standalone ASR Service

For advanced users or debugging:

```bash
python start_vr_asr.py --student-id "123" --video-id "01_1" --debug
```

## 📊 Features

### Student Management

- Simple login with name + student ID
- Persistent session storage
- Individual progress tracking
- Statistics dashboard

### Video System

- Progressive unlocking (complete videos to unlock next)
- VR video support
- Session tracking
- Completion status

### ASR & Evaluation

- Real-time speech transcription
- Automatic evaluation against ground truth
- Word Error Rate (WER) and Character Error Rate (CER)
- Similarity scoring
- Audio file preservation

### Progress Tracking

- Completion rates
- Average scores
- Individual video performance
- Attempt history
- Time tracking

## 🎬 Adding Videos

### 1. Add Video Files

Place video files in the `videos/` directory:

```
videos/
├── 01-1- My First Video.mp4
├── 02-1- Second Training Video.mp4
└── 03-1- Advanced Maneuvers.mp4
```

### 2. Create Ground Truth Data

Add corresponding ground truth files in `data/ground_truth/`:

```
data/ground_truth/
├── 01_1.txt
├── 02_1.txt
└── 03_1.txt
```

**Ground Truth Format**:

```
Tower this is Cessna 123 Alpha Bravo requesting taxi for departure
Ground control Cessna 123 Alpha Bravo taxi via Alpha taxiway hold short runway 7 Left
Cessna 123 Alpha Bravo taxi Alpha hold short runway 7 Left
```

### 3. Initialize Video Database

The backend automatically scans and initializes videos on startup.

## 🎛️ Configuration

### Backend Configuration

Edit `backend/main.py`:

- Database path
- API endpoints
- CORS settings

### ASR Configuration

Edit `src/asr_service_vr.py`:

- Whisper model settings
- VAD parameters
- Audio quality settings

### Frontend Configuration

Edit `web/assets/js/api.js`:

- Backend URL
- API endpoints
- Retry settings

## 📁 Directory Structure

```
asr-pipeline/
├── backend/                    # FastAPI backend
│   ├── api/routes/            # API endpoints
│   ├── database/              # Database management
│   ├── services/              # Business logic
│   └── main.py                # FastAPI app
├── web/                       # Frontend
│   ├── assets/                # CSS/JS/Images
│   └── index.html             # Main interface
├── src/                       # ASR services
│   ├── asr_service_vr.py      # VR-enhanced ASR
│   └── asr_evaluate.py        # Evaluation tools
├── data/                      # Application data
│   ├── ground_truth/          # Video ground truth
│   ├── asr_sessions/          # Session configs
│   └── vr_training.db         # SQLite database
├── audios/                    # Student audio files
│   └── {student_id}/          # Per-student directories
├── logs/                      # Application logs
│   └── students/              # Per-student logs
├── videos/                    # Training videos
└── start_*.py                 # Startup scripts
```

## 🔧 API Endpoints

### Authentication

- `POST /api/v1/auth/login` - Student login/registration
- `GET /api/v1/auth/validate/{student_id}` - Validate session
- `POST /api/v1/auth/logout/{student_id}` - Logout

### Students

- `GET /api/v1/students/{student_id}/progress` - Get progress
- `POST /api/v1/students/{student_id}/progress` - Update progress
- `GET /api/v1/students/{student_id}/statistics` - Get statistics
- `GET /api/v1/students/{student_id}/dashboard` - Dashboard data

### Videos

- `GET /api/v1/videos/student/{student_id}` - Get videos for student
- `GET /api/v1/videos/{video_id}/access/{student_id}` - Check access
- `POST /api/v1/videos/{video_id}/start-session/{student_id}` - Start session

### ASR

- `POST /api/v1/asr/start-session` - Start ASR session
- `POST /api/v1/asr/submit-result` - Submit transcription
- `POST /api/v1/asr/evaluate` - Evaluate transcript
- `GET /api/v1/asr/student/{student_id}/live-transcription` - Live data

## 💡 Usage Examples

### Basic Student Workflow

1. **Login**: Student enters name "John Doe" and ID "FL001"
2. **Dashboard**: Shows 13 videos, first one unlocked
3. **Start Video**: Click first video to open player
4. **Record**: Click "Start Recording" during video
5. **Speak**: Student practices radio communications
6. **Evaluate**: System shows real-time similarity scores
7. **Progress**: Complete video unlocks the next one

### Instructor Workflow

1. **Add Videos**: Place MP4 files in `videos/` directory
2. **Add Ground Truth**: Create `.txt` files with expected speech
3. **Monitor**: Check student progress via database/logs
4. **Analytics**: Review completion rates and scores

## 🐛 Debugging

### Check Backend Status

```bash
curl http://localhost:8000/health
```

### View Live ASR Output

```bash
tail -f logs/students/{student_id}/asr_results.jsonl
```

### Enable Debug Mode

```bash
ASR_DEBUG=1 python start_vr_asr.py --student-id "test_student"
```

### Database Inspection

```bash
sqlite3 data/vr_training.db
.tables
SELECT * FROM students LIMIT 5;
```

## 🔍 Troubleshooting

### Backend Won't Start

- Check Python dependencies: `pip install -r backend/requirements.txt`
- Verify port 8000 is available
- Check for permission errors in logs

### ASR Not Working

- Verify microphone permissions in browser
- Check audio device availability
- Ensure Whisper model is downloaded
- Review ASR service logs

### Frontend Issues

- Clear browser cache
- Check browser console for errors
- Verify backend API connectivity
- Try different browser

### No Ground Truth Evaluation

- Verify `.txt` files exist in `data/ground_truth/`
- Check file naming matches video IDs
- Ensure ground truth content is properly formatted

## 📈 Scaling Considerations

### Multiple Students

- Database supports unlimited students
- Each student gets individual directories
- Session management prevents conflicts

### Large Video Libraries

- Videos served directly as static files
- Database indexes on student_id and video_id
- Lazy loading of video metadata

### Performance Optimization

- Enable GPU acceleration for Whisper
- Use SSD storage for audio files
- Consider Redis for session caching

## 🔐 Security Notes

- **Local Only**: System designed for local deployment
- **No Authentication**: Simple name/ID login for ease of use
- **Data Privacy**: All data stays on local machine
- **File Access**: Static file serving limited to videos directory

## 📝 License

This VR Flight Training system extends the original ASR pipeline for educational use in flight training environments.
