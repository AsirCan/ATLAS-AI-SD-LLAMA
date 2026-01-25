# 🌍 ATLAS AI - Local Voice & Visual Assistant

**Atlas AI** is a fully local, agentic voice assistant capable of generating real-time visuals, news videos, and managing Instagram content using advanced AI models.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![React](https://img.shields.io/badge/React-18-blue?style=for-the-badge&logo=react)
![Stable Diffusion](https://img.shields.io/badge/Stable%20Diffusion-XL-orange?style=for-the-badge)
![Llama 3](https://img.shields.io/badge/LLM-Llama%203-blueviolet?style=for-the-badge)

## ✨ Features

- **🗣️ Voice Interaction:** Talk to Atlas naturally using Speech-to-Text and TTS (Fahrettin model).
- **🎨 Image Generation:** Creates high-quality images using Stable Diffusion XL (via Forge WebUI) based on conversation context.
- **📰 News Agent:** Fetches real-world news, writes scripts, generates visuals, and produces narrated video reports.
- **📸 Instagram Integration:** Can automatically upload generated content to Instagram as posts or carousels.
- **🧠 Local Intelligence:** Powered by Llama 3 (via Ollama) running entirely on your machine.
- **💻 Modern Web UI:** sleek, responsive React frontend.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed:

- **OS:** Windows 10/11 (Recommended)
- **GPU:** NVIDIA GPU with 8GB+ VRAM (Recommended for SDXL)
- **Software:**
  - [Python 3.10+](https://www.python.org/downloads/) (Make sure to check **"Add to PATH"**)
  - [Git](https://git-scm.com/)
  - [Node.js](https://nodejs.org/) (For the web interface)
  - [Ollama](https://ollama.com/) (For Llama 3)

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/AsirCan/ATLAS-AI-SD-LLAMA.git
cd ATLAS-AI-SD-LLAMA
```

### 2. Configure Credentials
**Critical Step:** This project uses a secure `.env` file for credentials.
1.  Copy the example file:
    ```bash
    copy .env.example .env
    ```
2.  Open `.env` with a text editor and fill in your details:
    ```ini
    INSTA_USERNAME=your_username
    INSTA_PASSWORD=your_password
    ```

### 3. Automated Install
Run the installer script to set up the virtual environment, download dependencies, and set up Stable Diffusion (Forge):
```bash
python install.py
```
*(This may take a while as it downloads large AI models.)*

### 4. Install Frontend Dependencies
```bash
cd web/frontend
npm install
cd ../..
```

## ▶️ Usage

To start Atlas (Backend + Frontend + Browser):

```bash
python run.py
```

- **Voice Command:** Say "Hey Atlas" to wake it up.
- **Web Interface:** Opens automatically at `http://localhost:5173`.

## 📂 Project Structure

```
├── core/               # Python backend logic (AI agents, config)
├── web/
│   ├── backend/        # FastAPI server
│   └── frontend/       # React application
├── models/             # Local AI models (STT/TTS)
├── install.py          # Setup script
└── run.py              # Launcher script
```

## 🛡️ Privacy & Security
- **Credentials:** Your Instagram password is strictly stored in your local `.env` file and is **never** uploaded to GitHub.
- **Local Processing:** All voice and image processing happens locally on your machine.

## 🤝 Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License
[MIT](https://choosealicense.com/licenses/mit/)