"""
Agent Loop Module
Implements the ReAct (Reasoning + Acting) agent loop
"""

import asyncio
import json
import logging
from typing import Optional, Set, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentState:
    status: AgentStatus = AgentStatus.IDLE
    current_step: int = 0
    total_steps: int = 0
    current_thought: str = ""
    current_action: str = ""
    last_result: str = ""
    objective: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ToolResult:
    def __init__(self, success: bool, result: Any, error: Optional[str] = None):
        self.success = success
        self.result = result
        self.error = error
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "result": str(self.result) if self.result else None,
            "error": self.error
        }


class AgentLoop:
    """
    Core ReAct Agent Loop implementation
    Reasoning + Acting cycle for autonomous task execution
    """
    
    def __init__(
        self,
        session_id: str,
        session_dir: str,
        model_router,
        playwright_tool,
        objective: str,
        max_iterations: int = 50
    ):
        self.session_id = session_id
        self.session_dir = session_dir
        self.model_router = model_router
        self.playwright_tool = playwright_tool
        self.objective = objective
        self.max_iterations = max_iterations
        
        # State management
        self.state = AgentState(objective=objective)
        self.status = AgentStatus.IDLE
        
        # Subscribers for WebSocket streaming
        self.log_subscribers: Set = set()
        self.screen_subscribers: Set = set()
        
        # Message queue for human-in-the-loop
        self.user_messages: asyncio.Queue = asyncio.Queue()
        
        # Conversation history for the LLM
        self.conversation_history: List[Dict[str, str]] = []
        
        # Available tools registry
        self.tools = self._build_tool_registry()
        
        # Pause event
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Initially not paused
        
        # Stop flag
        self._stop_flag = False
    
    def _build_tool_registry(self) -> Dict[str, callable]:
        """Build the tool registry with all available tools"""
        return {
            "browser_navigate": self.playwright_tool.navigate,
            "browser_click": self.playwright_tool.click,
            "browser_type": self.playwright_tool.type_text,
            "browser_scroll": self.playwright_tool.scroll,
            "browser_extract": self.playwright_tool.extract_data,
            "python_execute": self._execute_python,
            "file_upload": self._handle_file_upload,
            "final_answer": self._final_answer,
        }
    
    async def _log(self, message: str, log_type: str = "info"):
        """Send log message to all subscribers"""
        self.state.updated_at = datetime.now()
        log_entry = {
            "type": log_type,
            "message": message,
            "timestamp": self.state.updated_at.isoformat(),
            "step": self.state.current_step
        }
        
        # Broadcast to all log subscribers
        for subscriber in list(self.log_subscribers):
            try:
                await subscriber.send_json(log_entry)
            except Exception as e:
                logger.error(f"Error sending log to subscriber: {e}")
                self.log_subscribers.discard(subscriber)
    
    async def _update_state(self, **kwargs):
        """Update agent state and notify subscribers"""
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self.state.updated_at = datetime.now()
        
        # Notify state change
        await self._log(
            f"State updated: {json.dumps(kwargs)}",
            log_type="state_update"
        )
    
    async def add_user_message(self, content: str):
        """Add a user message to the queue for human-in-the-loop"""
        await self.user_messages.put({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        await self._log(f"User message received: {content}", log_type="user_message")
    
    async def pause(self):
        """Pause the agent loop"""
        self._pause_event.clear()
        self.status = AgentStatus.PAUSED
        self.state.status = AgentStatus.PAUSED
        await self._log("Agent paused", log_type="status_change")
    
    async def resume(self):
        """Resume the agent loop"""
        self._pause_event.set()
        self.status = AgentStatus.RUNNING
        self.state.status = AgentStatus.RUNNING
        await self._log("Agent resumed", log_type="status_change")
    
    async def stop(self):
        """Stop the agent loop permanently"""
        self._stop_flag = True
        self._pause_event.set()  # Unblock if paused
        self.status = AgentStatus.STOPPED
        self.state.status = AgentStatus.STOPPED
        
        # Cleanup playwright
        if self.playwright_tool:
            await self.playwright_tool.close()
        
        await self._log("Agent stopped", log_type="status_change")
    
    async def _execute_python(self, code: str) -> ToolResult:
        """Execute Python code in sandboxed environment"""
        import subprocess
        import tempfile
        import shlex
        
        try:
            # Create a temporary file for the code
            code_file = os.path.join(self.session_dir, f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
            
            # Security: Sanitize code - remove dangerous operations
            dangerous_patterns = [
                "__import__", "importlib", "subprocess", "os.system",
                "eval(", "exec(", "compile(", "open(/", "rm ", "sudo"
            ]
            for pattern in dangerous_patterns:
                if pattern in code:
                    return ToolResult(
                        success=False,
                        result=None,
                        error=f"Dangerous operation detected: {pattern}"
                    )
            
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Execute with timeout and resource limits
            result = subprocess.run(
                ["python3", code_file],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.session_dir
            )
            
            if result.returncode == 0:
                return ToolResult(success=True, result=result.stdout)
            else:
                return ToolResult(success=False, result=result.stdout, error=result.stderr)
                
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, result=None, error="Execution timeout (30s)")
        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
    
    async def _handle_file_upload(self, file_data: dict) -> ToolResult:
        """Handle file upload from user"""
        try:
            filename = file_data.get("filename", "uploaded_file")
            content = file_data.get("content", "")
            
            filepath = os.path.join(self.session_dir, filename)
            
            # Security: Validate filename
            if ".." in filename or filename.startswith("/"):
                return ToolResult(
                    success=False,
                    result=None,
                    error="Invalid filename"
                )
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            return ToolResult(success=True, result=f"File saved to {filepath}")
        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
    
    async def _final_answer(self, answer: str) -> ToolResult:
        """Deliver final answer to user"""
        await self._log(f"Final Answer: {answer}", log_type="final_answer")
        self.status = AgentStatus.COMPLETED
        self.state.status = AgentStatus.COMPLETED
        return ToolResult(success=True, result=answer)
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent"""
        return """You are an autonomous AI agent with the ability to control a web browser and execute code.
Your goal is to complete the user's objective by reasoning step-by-step and using the available tools.

Available Tools:
1. browser_navigate(url: str) - Navigate to a URL
2. browser_click(selector: str) - Click on an element (CSS selector)
3. browser_type(selector: str, text: str) - Type text into an input field
4. browser_scroll(direction: str) - Scroll up or down
5. browser_extract(format: str) - Extract data from page (JSON/HTML)
6. python_execute(code: str) - Execute Python code (sandboxed)
7. file_upload(filename: str, content: str) - Save a file to the workspace
8. final_answer(answer: str) - Provide the final result to the user

Rules:
- Think step-by-step before taking action
- Use one tool at a time
- Always observe the result of your actions
- If you encounter an error, try to recover or explain the issue
- When the task is complete, use final_answer to provide the result
- You can only access files within your designated workspace directory

Format your response as JSON:
{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {"param1": "value1", ...}
}

When the task is complete, use:
{
    "thought": "Task completed",
    "action": "final_answer",
    "action_input": {"answer": "Your final result"}
}
"""
    
    async def _get_llm_response(self, messages: List[Dict[str, str]]) -> Optional[Dict]:
        """Get response from LLM via model router"""
        try:
            response = await self.model_router.generate(messages)
            
            # Parse JSON response
            if isinstance(response, str):
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {"thought": response, "action": "final_answer", "action_input": {"answer": response}}
            
            return response
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return None
    
    async def run(self):
        """Main agent loop - ReAct cycle"""
        import os
        
        self.status = AgentStatus.RUNNING
        self.state.status = AgentStatus.RUNNING
        
        await self._log(f"Starting agent loop with objective: {self.objective}", log_type="info")
        
        # Initialize conversation with system prompt and objective
        self.conversation_history = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": f"Objective: {self.objective}"}
        ]
        
        iteration = 0
        
        try:
            while iteration < self.max_iterations and not self._stop_flag:
                iteration += 1
                self.state.current_step = iteration
                
                # Wait if paused
                await self._pause_event.wait()
                
                if self._stop_flag:
                    break
                
                # Check for user messages
                try:
                    while not self.user_messages.empty():
                        user_msg = await asyncio.wait_for(self.user_messages.get(), timeout=0.1)
                        self.conversation_history.append(user_msg)
                except asyncio.TimeoutError:
                    pass
                
                # Get LLM response
                await self._log(f"Step {iteration}: Thinking...", log_type="thought")
                llm_response = await self._get_llm_response(self.conversation_history)
                
                if not llm_response:
                    await self._log("Failed to get LLM response", log_type="error")
                    continue
                
                thought = llm_response.get("thought", "")
                action = llm_response.get("action", "")
                action_input = llm_response.get("action_input", {})
                
                self.state.current_thought = thought
                self.state.current_action = action
                
                await self._log(f"Thought: {thought}", log_type="thought")
                await self._log(f"Action: {action}({action_input})", log_type="action")
                
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": json.dumps(llm_response)
                })
                
                # Execute action
                if action not in self.tools:
                    await self._log(f"Unknown tool: {action}", log_type="error")
                    continue
                
                tool_func = self.tools[action]
                
                try:
                    if asyncio.iscoroutinefunction(tool_func):
                        result = await tool_func(**action_input)
                    else:
                        result = tool_func(**action_input)
                    
                    # Handle ToolResult
                    if isinstance(result, ToolResult):
                        result_dict = result.to_dict()
                    else:
                        result_dict = {"success": True, "result": str(result)}
                    
                    self.state.last_result = str(result_dict.get("result", ""))
                    
                    await self._log(f"Result: {result_dict}", log_type="result")
                    
                    # Add tool result to conversation history
                    self.conversation_history.append({
                        "role": "tool",
                        "name": action,
                        "content": json.dumps(result_dict)
                    })
                    
                    # Check if task is complete
                    if action == "final_answer":
                        await self._log("Task completed successfully", log_type="completion")
                        break
                        
                except Exception as e:
                    error_msg = f"Tool execution error: {str(e)}"
                    await self._log(error_msg, log_type="error")
                    self.conversation_history.append({
                        "role": "tool",
                        "name": action,
                        "content": json.dumps({"success": False, "error": error_msg})
                    })
            
            if iteration >= self.max_iterations:
                await self._log("Max iterations reached", log_type="warning")
                self.status = AgentStatus.COMPLETED
                
        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            await self._log(f"Fatal error: {str(e)}", log_type="error")
            self.status = AgentStatus.ERROR
            self.state.status = AgentStatus.ERROR
        
        finally:
            if self.status not in [AgentStatus.COMPLETED, AgentStatus.STOPPED, AgentStatus.ERROR]:
                self.status = AgentStatus.COMPLETED
                self.state.status = AgentStatus.COMPLETED


# Import os at module level for the methods that need it
import os
