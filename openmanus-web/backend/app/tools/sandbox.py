"""
Sandbox Module
Handles secure Python code execution with resource limits
"""

import os
import subprocess
import tempfile
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float


class Sandbox:
    """
    Secure Python code execution sandbox
    Implements timeouts, resource limits, and path restrictions
    """
    
    def __init__(
        self,
        session_dir: str,
        timeout: int = 30,
        max_memory_mb: int = 512
    ):
        self.session_dir = session_dir
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        
        # Ensure session directory exists
        os.makedirs(session_dir, exist_ok=True)
        
        # Dangerous patterns to block
        self.dangerous_patterns = [
            '__import__', 'importlib', 'subprocess', 'os.system',
            'os.popen', 'os.spawn', 'eval(', 'exec(', 'compile(',
            'open(/', 'rm ', 'sudo', 'chmod', 'chown', 'mkfs',
            'dd if=', '> /dev/', '/etc/', '/root/', '/boot/'
        ]
    
    def _sanitize_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Check code for dangerous operations
        Returns (is_safe, error_message)
        """
        for pattern in self.dangerous_patterns:
            if pattern in code:
                return False, f"Dangerous operation detected: {pattern}"
        
        return True, None
    
    def execute(
        self,
        code: str,
        cwd: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute Python code in sandboxed environment
        
        Args:
            code: Python code to execute
            cwd: Working directory (must be within session_dir)
        
        Returns:
            ExecutionResult with success status and output
        """
        import time
        
        # Validate working directory
        if cwd:
            abs_cwd = os.path.abspath(cwd)
            if not abs_cwd.startswith(os.path.abspath(self.session_dir)):
                return ExecutionResult(
                    success=False,
                    stdout='',
                    stderr='Working directory must be within session directory',
                    return_code=-1,
                    execution_time=0
                )
        else:
            cwd = self.session_dir
        
        # Sanitize code
        is_safe, error_msg = self._sanitize_code(code)
        if not is_safe:
            return ExecutionResult(
                success=False,
                stdout='',
                stderr=error_msg,
                return_code=-1,
                execution_time=0
            )
        
        # Create temporary file for code
        start_time = time.time()
        
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                dir=cwd,
                delete=False
            ) as f:
                f.write(code)
                temp_file = f.name
            
            # Set up resource limits (Unix only)
            preexec_fn = None
            if os.name != 'nt':
                def set_limits():
                    import resource
                    # Limit memory
                    memory_bytes = self.max_memory_mb * 1024 * 1024
                    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
                    # Limit CPU time
                    resource.setrlimit(resource.RLIMIT_CPU, (self.timeout, self.timeout))
                
                preexec_fn = set_limits
            
            # Execute code
            result = subprocess.run(
                ['python3', temp_file],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd,
                preexec_fn=preexec_fn,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                execution_time=execution_time
            )
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                stdout='',
                stderr=f'Execution timeout ({self.timeout}s)',
                return_code=-1,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                stdout='',
                stderr=str(e),
                return_code=-1,
                execution_time=execution_time
            )
        finally:
            # Clean up temp file
            try:
                if 'temp_file' in locals() and os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")
    
    def execute_with_dependencies(
        self,
        code: str,
        dependencies: list[str],
        cwd: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute code with required dependencies
        
        Note: In production, pre-install dependencies in the Docker image.
        This method assumes common data science libraries are available.
        """
        # For now, just execute the code directly
        # In a more advanced implementation, we could:
        # 1. Check if dependencies are installed
        # 2. Install missing ones in a virtual environment
        # 3. Execute code in that environment
        
        return self.execute(code, cwd)


# Async version for use in async contexts
class AsyncSandbox(Sandbox):
    """Async wrapper for Sandbox"""
    
    async def execute_async(
        self,
        code: str,
        cwd: Optional[str] = None
    ) -> ExecutionResult:
        """Execute code asynchronously"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, code, cwd)
    
    async def execute_with_dependencies_async(
        self,
        code: str,
        dependencies: list[str],
        cwd: Optional[str] = None
    ) -> ExecutionResult:
        """Execute code with dependencies asynchronously"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.execute_with_dependencies, 
            code, 
            dependencies, 
            cwd
        )
