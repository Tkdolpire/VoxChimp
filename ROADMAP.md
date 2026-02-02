# Nota Roadmap

## Vision

Transform Nota from a voice dictation tool into a comprehensive health monitoring system that:

1. Transcribes medical notes (current)
2. Analyzes voice/audio for health biomarkers (new - Google HEAR)
3. Extracts health insights from transcript content (new - NLP)
4. Integrates with Apple Health for holistic view (future)

---

## Phase 1: Audio Health Analysis with Google HEAR

### Overview

Google HEAR (Health Acoustic Representations) is a foundation model that generates health-optimized embeddings from audio. It can detect patterns in:

- Cough sounds (COVID, TB, respiratory conditions)
- Breathing patterns (COPD, asthma indicators)
- Voice characteristics (fatigue, stress, illness onset)

### Technical Approach

**Model Details:**

- Input: 2-second audio clips at 16kHz mono
- Output: 512-dimensional embedding vector per clip
- Architecture: Vision Transformer (ViT-L) based Masked Auto Encoder

**Integration Strategy:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     Nota Recording Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   User Records Audio                                            │
│         │                                                        │
│         ▼                                                        │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────┐  │
│   │ faster-     │     │   Google    │     │   Embedding     │  │
│   │ whisper     │     │    HEAR     │     │   Database      │  │
│   │(Transcript) │     │ (Embeddings)│     │  (Historical)   │  │
│   └──────┬──────┘     └──────┬──────┘     └────────┬────────┘  │
│          │                   │                      │           │
│          ▼                   ▼                      ▼           │
│   ~/.nota_history.json   ~/.nota_health/      Weekly/Monthly    │
│                          embeddings/           Analysis         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### 1.1 Enable Audio Archiving by Default

- Currently optional (`save_audio: false`)
- Make it default ON for health analysis
- Store in `~/.nota_audio/` with timestamps

#### 1.2 Add HEAR Model Integration

```python
# New file: health_analyzer.py

from huggingface_hub import from_pretrained_keras
import numpy as np
import librosa

class HealthAudioAnalyzer:
    def __init__(self):
        self.model = from_pretrained_keras("google/hear")
        self.serving = self.model.signatures['serving_default']

    def process_audio(self, audio_path):
        """Process audio file into 2-second chunks and get embeddings."""
        # Load and resample to 16kHz
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)

        # Split into 2-second chunks (32000 samples each)
        chunk_size = 32000
        chunks = []
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            if len(chunk) == chunk_size:
                chunks.append(chunk)

        if not chunks:
            return None

        # Get embeddings
        batch = np.array(chunks)
        embeddings = self.serving(x=batch)['output_0'].numpy()

        return {
            'embeddings': embeddings,  # Shape: (n_chunks, 512)
            'timestamp': datetime.now().isoformat(),
            'audio_file': audio_path,
            'n_chunks': len(chunks)
        }
```

#### 1.3 Create Embedding Storage

```python
# Store in ~/.nota_health/embeddings.json
{
    "sessions": [
        {
            "date": "2026-01-25",
            "audio_file": "~/.nota_audio/recording_20260125_151014.wav",
            "embeddings": [[0.123, 0.456, ...], ...],  # 512-dim vectors
            "transcript_id": 42
        }
    ]
}
```

#### 1.4 Build Analysis Pipeline

- **Daily**: Compute embeddings for new recordings
- **Weekly**: Analyze trends, compare to baseline
- **Alerts**: Detect significant deviations from personal baseline

### Dependencies to Add

```
tensorflow>=2.10
huggingface-hub
librosa
scipy
```

### Challenges

1. **Model Size**: HEAR is large (~1GB), may need lazy loading
2. **Processing Time**: Run analysis in background/scheduled
3. **Privacy**: All processing local, no cloud upload

---

## Phase 2: Transcript Content Analysis

### Overview

Analyze the TEXT content of transcripts for health-related mentions using NLP.

### What to Extract

- Symptoms mentioned (headache, fatigue, cough, pain)
- Medication references
- Mood indicators
- Sleep quality mentions
- Activity levels
- Stress indicators

### Technical Approach

**Option A: Local LLM (Ollama)**

```python
# Use local Ollama for privacy
import ollama

def analyze_transcript(text):
    response = ollama.chat(model='llama3', messages=[{
        'role': 'user',
        'content': f"""Analyze this medical note for health indicators.
        Extract: symptoms, medications, mood, sleep quality, stress level.
        Return JSON format.

        Note: {text}"""
    }])
    return json.loads(response['message']['content'])
```

**Option B: Keyword/Pattern Matching**

```python
SYMPTOM_PATTERNS = {
    'respiratory': ['cough', 'wheeze', 'shortness of breath', 'congestion'],
    'fatigue': ['tired', 'exhausted', 'no energy', 'fatigue'],
    'pain': ['headache', 'migraine', 'ache', 'sore'],
    'digestive': ['nausea', 'stomach', 'appetite'],
    'mental': ['stressed', 'anxious', 'depressed', 'overwhelmed']
}

def extract_symptoms(text):
    found = {}
    text_lower = text.lower()
    for category, keywords in SYMPTOM_PATTERNS.items():
        matches = [kw for kw in keywords if kw in text_lower]
        if matches:
            found[category] = matches
    return found
```

### Storage Schema

```json
// ~/.nota_health/insights.json
{
  "weekly_summaries": [
    {
      "week": "2026-W04",
      "symptom_counts": {
        "fatigue": 5,
        "headache": 2,
        "cough": 1
      },
      "mood_trend": "declining",
      "notable_patterns": ["fatigue mentioned 3 days in a row"]
    }
  ]
}
```

---

## Phase 3: Health Dashboard UI

### New Window: Health Insights

```
┌─────────────────────────────────────────────────────┐
│  Nota Health Insights                          [X]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  This Week (Jan 20-26)                             │
│  ─────────────────────                             │
│                                                     │
│  Voice Analysis (HEAR)                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ Baseline Deviation: +0.12 (normal range)    │   │
│  │ Trend: Stable                               │   │
│  │ [View Details]                              │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Transcript Mentions                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ Fatigue: ████████░░ 8 mentions              │   │
│  │ Headache: ██░░░░░░░░ 2 mentions             │   │
│  │ Stress: ████░░░░░░ 4 mentions               │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Recommendations                                   │
│  • Fatigue trending up - consider sleep review    │
│  • Voice patterns normal                          │
│                                                     │
│  [Export Report]  [Settings]  [Close]              │
└─────────────────────────────────────────────────────┘
```

---

## Phase 4: Apple Health Integration

### Overview

Export Nota health insights to Apple Health and import Apple Health data for correlation analysis.

### Apple Health Data to Import

- Sleep data (duration, quality)
- Heart rate / HRV
- Activity (steps, workouts)
- Respiratory rate
- Blood oxygen

### Correlation Analysis

```
┌──────────────────────────────────────────────────────┐
│  Correlation Analysis                                │
├──────────────────────────────────────────────────────┤
│                                                      │
│  When you mention "fatigue" in notes:               │
│  • Average sleep night before: 5.2 hrs (vs 7.1 avg)│
│  • HRV: 12% below baseline                         │
│  • Steps previous day: 2,100 (vs 6,500 avg)        │
│                                                      │
│  Voice biomarker changes detected 2-3 days before  │
│  you mentioned feeling unwell.                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Technical Approach

**HealthKit Integration via PyObjC:**

```python
from HealthKit import (
    HKHealthStore, HKQuantityType, HKQuantityTypeIdentifierStepCount,
    HKQuantityTypeIdentifierHeartRate, HKQuantityTypeIdentifierSleepAnalysis
)

class AppleHealthConnector:
    def __init__(self):
        self.store = HKHealthStore.alloc().init()

    def request_authorization(self):
        # Request read access to health data types
        read_types = [
            HKQuantityType.quantityTypeForIdentifier_(HKQuantityTypeIdentifierStepCount),
            HKQuantityType.quantityTypeForIdentifier_(HKQuantityTypeIdentifierHeartRate),
            # ... more types
        ]
        self.store.requestAuthorizationToShareTypes_readTypes_completion_(
            None, set(read_types), self._auth_callback
        )

    def fetch_sleep_data(self, start_date, end_date):
        # Query sleep analysis data
        ...
```

### Privacy Considerations

- All data stays local
- No cloud sync
- User controls what's analyzed
- Clear data deletion options

---

## Phase 5: iOS/iPad Mobile App (Server Architecture)

### Overview

Extend Nota to iOS and iPad by using a client-server architecture. The mobile app acts as a thin client that records audio and sends it to a self-hosted server running the existing Python stack.

### Why Server Architecture?

The current macOS tech stack cannot run on iOS:

| Component  | macOS (current)     | iOS Blocker              |
| ---------- | ------------------- | ------------------------ |
| Python     | Native              | Not allowed on App Store |
| PyObjC     | macOS Cocoa         | iOS uses UIKit/SwiftUI   |
| pynput     | System-wide hotkeys | iOS forbids this         |
| Auto-paste | Accessibility APIs  | No cross-app automation  |

### Architecture

```
┌─────────────────────┐         ┌─────────────────────────────┐
│   iOS/iPad App      │         │      Nota Server            │
│   (Swift/SwiftUI)   │         │   (existing Python stack)   │
│                     │  HTTPS  │                             │
│  • Record audio     │ ──────► │  • faster-whisper           │
│  • Send to API      │         │  • HEAR health analysis     │
│  • Display results  │ ◄────── │  • Transcript analysis      │
│  • View health data │         │  • Return JSON response     │
└─────────────────────┘         └─────────────────────────────┘
```

### Server API Endpoints

```python
# Flask/FastAPI backend

POST /api/transcribe
  - Input: audio file (WAV/M4A)
  - Output: { "text": "transcribed text", "duration": 3.2 }

POST /api/analyze
  - Input: audio file
  - Output: { "transcription": "...", "health_embeddings": [...], "symptoms": [...] }

GET /api/health/summary
  - Input: date range
  - Output: { "weekly_summary": {...}, "trends": {...} }

GET /api/history
  - Input: pagination params
  - Output: { "transcriptions": [...] }
```

### iOS App Features

- **SwiftUI interface** with large record button
- **AVFoundation** for audio capture
- **URLSession** for API communication
- **Copy to clipboard** for manual paste
- **Health dashboard** view synced from server
- **Offline queue** for recordings when no connection

### Implementation Steps

#### 5.1 Create API Server

```python
# notta_server.py
from fastapi import FastAPI, UploadFile
from notta import transcribe_audio
from health.audio_analyzer import HealthAudioAnalyzer

app = FastAPI()
analyzer = HealthAudioAnalyzer()

@app.post("/api/transcribe")
async def transcribe(audio: UploadFile):
    audio_data = await audio.read()
    result = transcribe_audio(audio_data)
    return {"text": result["text"], "duration": result["duration"]}

@app.post("/api/analyze")
async def analyze(audio: UploadFile):
    audio_data = await audio.read()
    transcription = transcribe_audio(audio_data)
    health_data = analyzer.process_audio(audio_data)
    return {
        "transcription": transcription["text"],
        "health_embeddings": health_data["embeddings"].tolist(),
        "timestamp": health_data["timestamp"]
    }
```

#### 5.2 Build iOS App

- Xcode project with SwiftUI
- Simple recording interface
- Server configuration (URL, auth token)
- Background upload support

#### 5.3 Authentication & Security

- API key or JWT authentication
- HTTPS only
- Optional: self-signed certs for local network

### Trade-offs

| Pros                                | Cons                         |
| ----------------------------------- | ---------------------------- |
| Reuse existing Python codebase      | Requires internet connection |
| Simple iOS app (App Store friendly) | Server hosting/maintenance   |
| Easy model updates server-side      | Latency (1-3 sec round trip) |
| Works on any iOS device             | Privacy: audio leaves device |
| Centralized health data             | Infrastructure costs         |

### Deployment Options

1. **Self-hosted** (Raspberry Pi, home server, NAS)
2. **VPS** (DigitalOcean, Linode, Hetzner)
3. **Cloud** (AWS, GCP with auto-scaling)

### Dependencies (Server)

```
fastapi
uvicorn
python-multipart
# Plus existing Nota dependencies
```

---

## Implementation Priority

| Phase | Feature                    | Effort | Impact    | Priority |
| ----- | -------------------------- | ------ | --------- | -------- |
| 1.1   | Audio archiving default ON | Low    | High      | P0       |
| 1.2   | HEAR model integration     | Medium | High      | P0       |
| 1.3   | Embedding storage          | Low    | Medium    | P0       |
| 1.4   | Weekly analysis job        | Medium | High      | P1       |
| 2.1   | Symptom extraction         | Low    | Medium    | P1       |
| 2.2   | Local LLM analysis         | Medium | High      | P2       |
| 3.1   | Health dashboard UI        | High   | High      | P2       |
| 4.1   | Apple Health read          | High   | Very High | P3       |
| 4.2   | Correlation analysis       | High   | Very High | P3       |
| 5.1   | API server                 | Medium | High      | P4       |
| 5.2   | iOS app                    | Medium | High      | P4       |
| 5.3   | Authentication             | Low    | Medium    | P4       |

---

## File Structure (Proposed)

```
Nota/
├── nota.py                    # Main app (existing)
├── health/
│   ├── __init__.py
│   ├── audio_analyzer.py      # HEAR model wrapper
│   ├── transcript_analyzer.py # NLP/keyword extraction
│   ├── embedding_store.py     # Embedding database
│   ├── weekly_report.py       # Scheduled analysis
│   └── apple_health.py        # HealthKit integration
├── ui/
│   ├── main_window.py         # Refactored from nota.py
│   └── health_dashboard.py    # New health insights window
└── data/
    └── symptom_patterns.json  # Keyword dictionaries
```

---

## Open Questions

1. **Processing Schedule**: When to run HEAR analysis?
   - Real-time (after each recording) - resource intensive
   - Batch (nightly) - delayed insights
   - On-demand (user triggered)

2. **Baseline Establishment**: How long to collect data before alerting?
   - Suggest: 2-4 weeks of recordings for personal baseline

3. **Alert Threshold**: What deviation triggers a health alert?
   - Need research on HEAR embedding distances

4. **Model Updates**: How to handle HEAR model updates?
   - Re-process historical audio?
   - Version embeddings?

---

## Next Steps

1. [ ] Enable `save_audio: true` by default
2. [ ] Create `health/` module structure
3. [ ] Implement HEAR model loading (lazy, on first analysis)
4. [ ] Build embedding storage schema
5. [ ] Create simple weekly analysis script
6. [ ] Add "Health" button to main UI
