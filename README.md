# STEMBeats
A STEM music app that separates audio into different tracks, such as drums, bass, piano, and vocals
# 🎵 STEMBeats

> **Separate. Isolate. Create.**

STEMBeats is an AI-powered music stem separation web app that splits any audio track into its individual components — **Drums**, **Bass**, **Piano**, and **Vocals** — giving producers, musicians, and audio engineers unprecedented control over their music.

---

## 🚀 Features

- **AI Stem Separation** — Upload any MP3, WAV, FLAC, or AAC file and split it into 4 isolated stems using state-of-the-art ML models (Spleeter / Demucs)
- **Interactive Stem Players** — Play, mute, solo, and adjust volume for each stem independently
- **10-Band Master EQ** — Fine-tune frequencies from 32Hz to 16kHz with preset profiles (Bass Boost, Vocal Enhance, Treble Boost)
- **FX Chain** — Apply real-time effects: Reverb, Echo/Delay, Pitch Shift, and Noise Gate
- **Animated Waveform Visualizer** — Color-coded frequency visualizer that pulses in real time
- **Export Options** — Download individual stems or a custom mix as MP3 or ZIP
- **Responsive Design** — Fully functional on desktop and mobile

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML5, CSS3 (glassmorphism), Vanilla JavaScript |
| Audio Separation | Python, Spleeter or Demucs |
| Backend API | Flask / FastAPI |
| Audio Processing | librosa, pydub, ffmpeg |
| Storage | Local filesystem / AWS S3 (optional) |
| Deployment | Docker, Render / Railway / AWS |

---

## 📁 Project Structure

```
STEMBeats/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── backend/
│   ├── app.py
│   ├── separator.py
│   ├── effects.py
│   └── requirements.txt
├── models/
├── uploads/
├── outputs/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── README.md
└── .gitignore
```

---

## ⚙️ Getting Started

### Prerequisites

- Python 3.8+
- ffmpeg installed on your system
- 4GB+ RAM (for ML model inference)

### 1. Clone the Repository

```bash
git clone https://github.com/80Kane/STEMBeats.git
cd STEMBeats
```

### 2. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Run the Backend Server

```bash
python app.py
# Server starts at http://localhost:5000
```

### 4. Open the Frontend

```bash
python -m http.server 3000
# Open http://localhost:3000
```

---

## 🎛️ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/separate` | Upload audio file, returns job ID |
| `GET` | `/api/status/{job_id}` | Poll separation progress (0-100%) |
| `GET` | `/api/stems/{job_id}` | Download separated stem files |
| `POST` | `/api/export` | Export custom mix with applied FX |
| `DELETE` | `/api/cleanup/{job_id}` | Remove temporary files |

---

## 🗺️ Roadmap

- [x] UI Prototype (Stem Players, EQ, FX Chain, Waveform Visualizer)
- [ ] Flask backend with Spleeter integration
- [ ] Real-time progress websocket
- [ ] User accounts and project history
- [ ] Cloud storage integration (S3)
- [ ] Mobile app (React Native)
- [ ] Collaborative editing (multi-user sessions)
- [ ] VST plugin export
- [ ] MIDI extraction from stems

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 👤 Author

**Timothy Rollings Jr** ([@80Kane](https://github.com/80Kane))  
Rollings 7 Legacy Media

---

*Built with love for musicians, producers, and audio engineers.*
