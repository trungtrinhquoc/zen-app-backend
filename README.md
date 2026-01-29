# 🧘 Zen APP Backend

AI Backend for Zen APP - Emotional Support Companion

## 🚀 Tech Stack

- **Framework:** FastAPI (Python 3.11+)
- **Database:** Supabase (PostgreSQL + pgvector)
- **AI:** OpenAI GPT-4o-mini
- **Voice:** OpenAI TTS + Groq Whisper
- **Auth:** Supabase Auth

## 📦 Setup (Windows)

### Prerequisites

- Python 3.11+
- Poetry
- Git

### Installation

```powershell
# Clone repository
git clone https://github.com/trinhquoctrung/zen-app-backend.git
cd zen-app-backend

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Copy environment variables
copy .env.example .env
# Edit .env with your credentials

# Run development server
uvicorn app.main:app --reload
```

## 🗂️ Project Structure

```
app/
├── api/v1/          # API endpoints
├── core/            # Configuration
├── modules/         # 6 AI modules
├── models/          # Database models
├── schemas/         # Pydantic schemas
├── services/        # Shared services
└── utils/           # Utilities
```

## 📝 API Documentation

After running the server, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 Testing

```powershell
poetry run pytest
```

## 📄 License

MIT