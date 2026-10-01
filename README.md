# 📄 RAG PDF Reader

Upload one or more PDFs and ask questions about them. Answers are generated only from your documents, with page citations.

Built with **React + Tailwind** (frontend), **FastAPI** (backend), **Gemini** (LLM + embeddings) and **Qdrant** (vector database).

---

## ✨ Features

- Upload PDFs and chat with them
- **Multiple PDFs**: keep many documents, ask about one, several, or all at once
- **Automatic model switching**: when a model runs out of quota/tokens, the app falls back to the next model in the chain
- Streaming answers (text appears word by word)
- Page citations under every answer
- "I don't know" when the answer isn't in the document
- Chat history for follow-up questions

---

## 🧱 Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React (Vite), Tailwind CSS |
| Backend | FastAPI (Python) |
| LLM | Gemini (Flash models, with fallback chain) |
| Embeddings | `gemini-embedding-2` (768 dimensions) |
| Vector DB | Qdrant (Docker) |
| PDF parsing | `pypdf` or `PyMuPDF` |

---

## 🏗️ Architecture

```
            ┌──────────── UPLOAD ────────────┐
 React ──▶  FastAPI ──▶ ingest.py
 (PDF)                    │  extract text (per page)
                          │  split into chunks
                          │  embed (gemini-embedding-2)
                          ▼
                       Qdrant  (payload: doc_id, page, text)

            ┌──────────── QUESTION ──────────┐
 React ──▶  FastAPI ──▶ retrieve.py ──▶ Qdrant (filter by doc_id(s))
 (question)               │  top-k chunks
                          ▼
                        llm.py ──▶ Gemini (model chain w/ fallback)
                          │
                          ▼
              streamed answer + sources ──▶ React
```

---

## 📁 Folder Structure

```
rag-pdf/
├── README.md
├── docker-compose.yml            # Qdrant
├── .gitignore
│
├── backend/
│   ├── .env                      # secrets (never commit)
│   ├── .env.example              # template for .env
│   ├── requirements.txt
│   ├── main.py                   # FastAPI app, CORS, router registration
│   │
│   ├── app/
│   │   ├── config.py             # loads env vars (keys, model chain, chunk sizes)
│   │   ├── schemas.py            # Pydantic request/response models
│   │   │
│   │   ├── routes/
│   │   │   ├── documents.py      # upload / list / delete PDFs
│   │   │   └── chat.py           # streaming chat endpoint
│   │   │
│   │   ├── core/                 # ⭐ GenAI part (written by you)
│   │   │   ├── ingest.py         # PDF -> chunks -> embeddings -> Qdrant
│   │   │   ├── retrieve.py       # question -> top-k chunks (doc filter)
│   │   │   ├── llm.py            # prompt + Gemini streaming answer
│   │   │   └── model_router.py   # model fallback logic (see below)
│   │   │
│   │   ├── services/
│   │   │   ├── qdrant_client.py  # Qdrant connection + collection setup
│   │   │   └── doc_store.py      # document registry (metadata of uploaded PDFs)
│   │   │
│   │   └── mocks/                # fake versions of core/ so UI works early
│   │       └── mock_core.py
│   │
│   ├── data/
│   │   ├── uploads/              # saved PDF files
│   │   └── documents.json        # registry: doc_id, filename, pages, chunks
│   │
│   └── tests/
│       ├── test_api.py           # route tests
│       ├── test_ingest.py        # chunking / embedding tests
│       ├── test_retrieve.py      # doc filtering tests
│       └── test_model_router.py  # fallback tests
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/
        │   └── client.js         # fetch wrappers + SSE streaming reader
        ├── components/
        │   ├── Sidebar.jsx       # document list, select/deselect, delete
        │   ├── UploadBox.jsx     # drag & drop PDF upload
        │   ├── ChatWindow.jsx    # messages + input
        │   ├── MessageBubble.jsx # user / assistant message
        │   ├── SourceChips.jsx   # "Page 4" citation chips
        │   └── ModelBadge.jsx    # shows which model answered
        ├── hooks/
        │   ├── useDocuments.js
        │   └── useChat.js
        └── styles/
            └── index.css         # Tailwind directives
```

---

## 📚 Multiple PDFs

### How documents are kept separate

We use **one Qdrant collection** and tag every chunk with the document it came from:

```json
{
  "doc_id": "a1b2c3",
  "filename": "physics-notes.pdf",
  "page": 4,
  "text": "chunk text here..."
}
```

A **payload index** is created on `doc_id` so filtering is fast.

> Why one collection instead of one per PDF? Simpler to manage, and it lets you search across several PDFs in a single query. Separation is done with filters, not with separate collections.

### Query modes

| Mode | Behaviour | Qdrant filter |
|---|---|---|
| Single PDF | Ask about one document | `doc_id == X` |
| Selected PDFs | Ask across chosen documents | `doc_id in [X, Y]` (`MatchAny`) |
| All PDFs | Ask across everything | no filter |

The sidebar shows all uploaded PDFs with checkboxes. Whatever is checked is sent to the backend as `doc_ids`.

### Citations across PDFs

Each source includes the filename, so answers show `physics-notes.pdf · page 4`.

### Deleting a PDF

`DELETE /api/documents/{doc_id}` removes:
1. the saved file in `data/uploads/`
2. its entry in `documents.json`
3. all its vectors in Qdrant (delete by `doc_id` filter)

---

## 🔄 Automatic Model Switching

When a model hits its quota (free-tier tokens/requests per minute or per day), Gemini returns a `429 RESOURCE_EXHAUSTED` error. Instead of failing, the app switches to the next model.

### Configuration

In `backend/.env`:

```env
GEMINI_API_KEY=your_key_here

# Ordered by priority: first = preferred, rest = fallbacks
# (replace with model names currently available in Google AI Studio)
CHAT_MODELS=gemini-2.5-flash,gemini-2.5-flash-lite

# How long to skip an exhausted model before trying it again (seconds)
MODEL_COOLDOWN_SECONDS=60

# Optional: extra API keys to rotate through if all models are exhausted
GEMINI_API_KEY_BACKUP=
```

### Logic (`model_router.py`)

```
for each model in CHAT_MODELS (skipping models on cooldown):
    try to generate the answer
    if success            -> return answer (and report which model answered)
    if 429 / quota error  -> mark model as "cooling down", try the next one
    if other error        -> raise (don't hide real bugs)

if every model is exhausted:
    return a friendly error: "All models are at their limit. Try again in ~X seconds."
```

Rules to keep it safe:
- Only **quota/rate-limit errors** trigger a switch. Other errors (bad prompt, invalid key) should surface normally.
- An exhausted model goes on a **cooldown timer** so we don't retry it on every request.
- The UI shows a small **model badge** ("answered by gemini-2.5-flash-lite") so the switch is visible.
- Streaming caveat: if a model fails **before** the first token, switch silently. If it fails **mid-stream**, either restart on the next model or show an error, your choice.

### ⚠️ Important: embeddings cannot be switched freely

Fallback works for the **chat model** only.

Every embedding model produces vectors in its own space. If documents were embedded with `gemini-embedding-2` and you embed a question with a different model, the search results will be meaningless, even if the dimensions match.

So for embeddings:
- Use **one embedding model for everything** (ingest and query).
- If embedding quota runs out, **wait/retry with backoff** or use a backup API key (same model).
- If you ever change the embedding model, **re-embed all documents** into a new collection.

---

## 🔌 API Endpoints

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/documents` | Upload a PDF (multipart). Returns `doc_id`, pages, chunks |
| `GET` | `/api/documents` | List all uploaded documents |
| `DELETE` | `/api/documents/{doc_id}` | Delete a document and its vectors |
| `POST` | `/api/chat` | Ask a question, streams the answer |
| `GET` | `/api/health` | Health check (backend + Qdrant) |

### Chat request

```json
{
  "question": "What is Newton's second law?",
  "doc_ids": ["a1b2c3", "d4e5f6"],
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

### Chat stream (Server-Sent Events)

```
event: token    data: {"text": "Newton's second law states..."}
event: token    data: {"text": " that force equals..."}
event: sources  data: [{"filename": "physics.pdf", "page": 4, "score": 0.82}]
event: model    data: {"name": "gemini-2.5-flash"}
event: done     data: {}
```

---

## 🤝 Function Contract (`core/`)

These are the functions the API layer calls. Keep the signatures and everything plugs in.

```python
# core/ingest.py
def ingest_pdf(file_path: str, doc_id: str, filename: str) -> dict:
    """Extract, chunk, embed, store in Qdrant.
    Returns: {"doc_id": str, "pages": int, "chunks": int}"""

# core/retrieve.py
def retrieve(question: str, doc_ids: list[str] | None, top_k: int = 5) -> list[dict]:
    """doc_ids=None searches all documents.
    Returns: [{"text": str, "page": int, "filename": str, "doc_id": str, "score": float}]"""

# core/llm.py
def generate_answer_stream(question: str, chunks: list[dict], history: list[dict]):
    """Generator yielding answer text pieces.
    Uses model_router internally for fallback."""

# core/model_router.py
def stream_with_fallback(prompt: str):
    """Yields (model_name, text_piece). Handles quota errors and cooldowns."""
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- Docker
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### 2. Start Qdrant

```bash
docker compose up -d
# Qdrant dashboard: http://localhost:6333/dashboard
```

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then add your GEMINI_API_KEY
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

### `docker-compose.yml`

```yaml
services:
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```

### `requirements.txt` (starting point)

```
fastapi
uvicorn[standard]
python-multipart
python-dotenv
pydantic
pypdf
google-genai
qdrant-client
pytest
httpx
```

---

## 🧪 Testing

```bash
cd backend
pytest -v
```

Key things tested:
- Upload, list, delete routes
- Chunking (size, overlap, page numbers preserved)
- Retrieval filters (single / multiple / all PDFs)
- Model fallback (simulated `429` moves to next model, cooldown works, non-quota errors are not swallowed)

---