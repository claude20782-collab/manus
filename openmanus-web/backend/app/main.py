"""
OpenManus-Web Backend Application
Main FastAPI application entry point
"""

import os
import asyncio
import logging
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent.agent_loop import AgentLoop, AgentState
from app.tools.playwright_tool import PlaywrightTool
from app.models.router import ModelRouter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global session storage
sessions: Dict[str, AgentLoop] = {}


class SessionStartRequest(BaseModel):
    objective: str
    model_provider: str  # "openai", "anthropic", "google", "ollama"
    model_name: str
    api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None


class SessionControlRequest(BaseModel):
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("OpenManus-Web backend starting...")
    
    # Ensure session directory exists
    session_dir = os.getenv("SESSION_DIR", "/workspace/sessions")
    os.makedirs(session_dir, exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down OpenManus-Web backend...")
    # Clean up all sessions
    for session_id, session in list(sessions.items()):
        await session.stop()
    sessions.clear()


app = FastAPI(
    title="OpenManus-Web API",
    description="Autonomous AI Agent with Browser Automation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/session/start")
async def start_session(request: SessionStartRequest):
    """Initialize a new agent session"""
    import uuid
    
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(os.getenv("SESSION_DIR", "/workspace/sessions"), session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Initialize model router
    model_config = {
        "provider": request.model_provider,
        "model": request.model_name,
        "api_key": request.api_key,
        "ollama_base_url": request.ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    }
    model_router = ModelRouter(model_config)
    
    # Initialize playwright tool
    playwright_tool = PlaywrightTool(session_id=session_id, session_dir=session_dir)
    
    # Create agent loop
    agent_loop = AgentLoop(
        session_id=session_id,
        session_dir=session_dir,
        model_router=model_router,
        playwright_tool=playwright_tool,
        objective=request.objective
    )
    
    sessions[session_id] = agent_loop
    
    # Start the agent loop in background
    asyncio.create_task(agent_loop.run())
    
    return {
        "session_id": session_id,
        "status": "started",
        "objective": request.objective
    }


@app.post("/api/session/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause the agent loop"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    await session.pause()
    
    return {"status": "paused", "session_id": session_id}


@app.post("/api/session/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume the agent loop"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    await session.resume()
    
    return {"status": "resumed", "session_id": session_id}


@app.post("/api/session/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop and cleanup the agent session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    await session.stop()
    del sessions[session_id]
    
    return {"status": "stopped", "session_id": session_id}


@app.post("/api/session/{session_id}/message")
async def send_message(session_id: str, message: dict):
    """Send additional instruction to running agent"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    await session.add_user_message(message.get("content", ""))
    
    return {"status": "message_received"}


@app.websocket("/ws/session/{session_id}/logs")
async def websocket_logs(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming agent logs and thought process"""
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    session = sessions[session_id]
    
    try:
        # Register this websocket connection
        session.log_subscribers.add(websocket)
        
        # Send initial state
        await websocket.send_json({
            "type": "state",
            "data": session.state.model_dump() if hasattr(session.state, 'model_dump') else session.state.__dict__
        })
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                # Handle incoming messages from client if needed
            except WebSocketDisconnect:
                break
    finally:
        session.log_subscribers.discard(websocket)
        await websocket.close()


@app.websocket("/ws/session/{session_id}/screen")
async def websocket_screen(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming live browser screenshots"""
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    session = sessions[session_id]
    
    try:
        # Register screen subscriber
        session.screen_subscribers.add(websocket)
        
        # Start screen streaming
        while True:
            try:
                # Check if agent has a current screenshot
                if session.playwright_tool and session.playwright_tool.current_screenshot:
                    screenshot_data = session.playwright_tool.current_screenshot
                    await websocket.send_bytes(screenshot_data)
                
                # Small delay to control FPS (target ~15 FPS)
                await asyncio.sleep(1/15)
                
            except WebSocketDisconnect:
                break
    finally:
        session.screen_subscribers.discard(websocket)
        await websocket.close()


@app.get("/api/session/{session_id}/files")
async def list_files(session_id: str):
    """List files in the session sandbox directory"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    session_dir = session.session_dir
    
    files = []
    for root, dirs, filenames in os.walk(session_dir):
        for filename in filenames:
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, session_dir)
            files.append({
                "name": rel_path,
                "size": os.path.getsize(filepath),
                "path": filepath
            })
    
    return {"files": files}


@app.get("/api/session/{session_id}/file/{file_path:path}")
async def get_file(session_id: str, file_path: str):
    """Get a specific file from the session sandbox"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    full_path = os.path.join(session.session_dir, file_path)
    
    # Security check: ensure path is within session directory
    if not full_path.startswith(session.session_dir):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(full_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
