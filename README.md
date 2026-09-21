# Voice Integrity AI — AASIST Deepfake Voice Authenticity System

Voice Integrity is a technology product application for AI voice deepfake detection and spectro-temporal voice authenticity analysis.

---

## 📁 Dataset & AI Backend Pipeline

### 1. Organize your Dataset
Create a dataset directory with your authentic human and AI voice clone audio files:

```text
my_dataset/
├── human/          # Put authentic human voice audio files (.wav, .mp3, .flac)
│   ├── human_01.wav
│   └── human_02.wav
└── synthetic/      # Put AI-generated voice clones (.wav, .mp3, .flac)
    ├── ai_clone_01.wav
    └── ai_clone_02.wav
```

---

### 2. Install Backend Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

---

### 3. Train the AASIST Model on your Dataset
Run the training script pointing to your dataset folder:

```bash
python train.py --data_dir /path/to/my_dataset --epochs 15 --batch_size 8
```
This will train the `AASISTVoiceClassifier` PyTorch model and save the weights to `backend/models/aasist_model.pt`.

---

### 4. Launch the FastAPI AI Server
```bash
python main.py
```
The server will start on **`http://localhost:8000`**. The React frontend will automatically connect to it for real-time model inference!

---

## ⚡ React Frontend Setup

```bash
# Install frontend dependencies
npm install

# Start Vite dev server
npm run dev

# Build for production
npm run build
```


