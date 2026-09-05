# OpenManus-Web

A production-ready autonomous AI agent web application inspired by Manus.ai. Features browser automation, code execution, and real-time screen streaming with support for multiple LLM providers.

## Features

### Core Capabilities
- **Autonomous AI Agent**: ReAct (Reasoning + Acting) loop for intelligent task execution
- **Browser Automation**: Full Playwright-based browser control (navigate, click, type, scroll, extract)
- **Live Screen Streaming**: Real-time browser view at 15+ FPS via WebSocket
- **Code Execution**: Sandboxed Python execution with pandas, numpy, matplotlib support
- **Multi-Model Support**: 
  - Cloud: OpenAI GPT-4o, Anthropic Claude 3.5, Google Gemini
  - Local: Ollama (Llama 3.1, Qwen 2.5, etc.), LM Studio compatible
- **Human-in-the-Loop**: Pause/resume agent, send mid-task instructions
- **File Workspace**: Isolated session directories for file operations

### Technical Highlights
- **Real-time Communication**: Dual WebSocket streams (logs + screen)
- **Security**: Sandboxed execution, path validation, API key isolation
- **Scalable Architecture**: Docker Compose setup with Redis queue support
- **Modern UI**: Next.js 14, TypeScript, Tailwind CSS, Zustand state management

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)
- Ollama (optional, for local LLM)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd openmanus-web
```

2. **Create environment file**
```bash
cp .env.example .env
```

3. **Configure environment variables**
```bash
# Optional: Set your API keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Ollama configuration (default works out of box)
OLLAMA_BASE_URL=http://ollama:11434
```

4. **Start all services**
```bash
docker-compose up -d
```

5. **Access the application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Ollama: http://localhost:11434
- Redis: localhost:6379

### First Session

1. Open http://localhost:3000 in your browser
2. Enter your objective (e.g., "Navigate to example.com and extract the title")
3. Select model provider:
   - **Ollama** (recommended for testing): Use `llama3.1` or any pulled model
   - **OpenAI**: Enter your API key, select `gpt-4o`
   - **Anthropic**: Enter API key, select `claude-3-5-sonnet-20241022`
   - **Google**: Enter API key, select `gemini-pro`
4. Click "Start Agent"
5. Watch the agent execute tasks in real-time!

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Next.js   │◄───►│   FastAPI    │◄───►│  Playwright │
│  Frontend   │ WS  │   Backend    │ HTTP│   Browser   │
│  (Port 3000)│     │  (Port 8000) │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
              ┌─────▼─────┐ ┌────▼────┐
              │   Redis   │ │ Ollama  │
              │  (Queue)  │ │  (LLM)  │
              └───────────┘ └─────────┘
```

### Component Overview

#### Backend (`/backend`)
- `app/main.py`: FastAPI application, REST + WebSocket endpoints
- `app/agent/agent_loop.py`: ReAct agent implementation
- `app/tools/playwright_tool.py`: Browser automation
- `app/tools/sandbox.py`: Code execution sandbox
- `app/models/router.py`: Multi-provider LLM routing

#### Frontend (`/frontend`)
- `app/page.tsx`: Main dashboard (3-column layout)
- `app/components/ScreenViewer.tsx`: Live screen stream renderer
- `app/lib/store.ts`: Zustand state management
- `app/hooks/useWebSocket.ts`: WebSocket connection hooks

## API Reference

### REST Endpoints

#### Start Session
```bash
POST /api/session/start
Content-Type: application/json

{
  "objective": "Your task description",
  "model_provider": "ollama|openai|anthropic|google",
  "model_name": "llama3.1|gpt-4o|...",
  "api_key": "optional_for_cloud",
  "ollama_base_url": "http://ollama:11434"
}
```

#### Control Session
```bash
POST /api/session/{id}/pause
POST /api/session/{id}/resume
POST /api/session/{id}/stop
POST /api/session/{id}/message
```

#### Get Files
```bash
GET /api/session/{id}/files
GET /api/session/{id}/file/{path}
```

### WebSocket Endpoints

#### Logs Stream
```
WS /ws/session/{id}/logs
```
Receives: Agent thoughts, actions, results, status changes

#### Screen Stream
```
WS /ws/session/{id}/screen
```
Receives: Binary JPEG frames (15 FPS)

## Available Tools

The agent can use these tools autonomously:

1. **browser_navigate(url)**: Go to a webpage
2. **browser_click(selector)**: Click element (CSS selector)
3. **browser_type(selector, text)**: Type into input
4. **browser_scroll(direction)**: Scroll up/down
5. **browser_extract(format)**: Extract JSON/HTML data
6. **python_execute(code)**: Run Python (sandboxed)
7. **file_upload(filename, content)**: Save file
8. **final_answer(answer)**: Complete task

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GOOGLE_API_KEY` | Google API key | - |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://ollama:11434` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `SESSION_DIR` | Session storage | `/workspace/sessions` |
| `ALLOWED_ORIGINS` | CORS origins | `http://localhost:3000` |

### Model Configuration

#### Using Ollama (Local)
```bash
# Pull a model first
docker exec openmanus-web-ollama-1 ollama pull llama3.1

# Or use your local Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

#### Using Cloud Providers
```bash
# OpenAI
export OPENAI_API_KEY=sk-...
# Model: gpt-4o, gpt-4-turbo, gpt-3.5-turbo

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
# Model: claude-3-5-sonnet-20241022, claude-3-opus

# Google
export GOOGLE_API_KEY=...
# Model: gemini-pro, gemini-ultra
```

## Development

### Running Locally (without Docker)

#### Backend
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Building Custom Images

```bash
docker-compose build
```

### Testing

```bash
# Backend tests (coming soon)
pytest backend/tests

# Frontend tests (coming soon)
npm test
```

## Security Considerations

- **Sandboxed Execution**: Python code runs with restricted permissions
- **Path Validation**: File access limited to session directory
- **API Key Isolation**: Keys stored in memory per-session only
- **CORS Protection**: Configurable allowed origins
- **No-Sandbox Browser**: Playwright runs with `--no-sandbox` in containers (use seccomp profiles in production)

### Production Deployment

For production use:
1. Enable proper seccomp profiles for browser sandboxing
2. Use HTTPS/WSS for all connections
3. Implement rate limiting
4. Add authentication/authorization
5. Configure resource limits (CPU, memory)
6. Set up monitoring and logging

## Troubleshooting

### Common Issues

**Browser won't start**
```bash
# Ensure Playwright browsers are installed
docker-compose run backend playwright install chromium
docker-compose run backend playwright install-deps chromium
```

**Ollama connection failed**
```bash
# Check Ollama is running
docker-compose ps ollama

# Pull a model if needed
docker exec -it openmanus-web-ollama-1 ollama pull llama3.1
```

**WebSocket connection errors**
- Verify `NEXT_PUBLIC_WS_URL` matches your backend URL
- Check firewall/proxy settings
- Ensure backend is accessible from frontend

**High memory usage**
- Reduce screen streaming FPS in `main.py`
- Limit max iterations in agent loop
- Stop idle sessions

## Roadmap

- [ ] Multi-agent collaboration
- [ ] Persistent memory/knowledge base
- [ ] Advanced planning (Tree of Thoughts, etc.)
- [ ] Mobile-responsive UI
- [ ] Session recording/playback
- [ ] Plugin system for custom tools
- [ ] Enhanced security with containerization
- [ ] Analytics and performance metrics

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Inspired by [Manus.ai](https://manus.ai)
- Built with [FastAPI](https://fastapi.tiangolo.com), [Next.js](https://nextjs.org), [Playwright](https://playwright.dev)
- LLM integration via [Ollama](https://ollama.ai), [OpenAI](https://openai.com), [Anthropic](https://anthropic.com), [Google AI](https://ai.google)

---

**Ready to automate?** Start your first agent session now! 🚀
