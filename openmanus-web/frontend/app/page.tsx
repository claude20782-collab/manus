'use client';

import { useEffect, useState } from 'react';
import { Play, Pause, Square, Send, Upload, FileText, Monitor, MessageSquare, Settings } from 'lucide-react';
import { marked } from 'marked';
import ScreenViewer from './components/ScreenViewer';
import { useAgentStore } from './lib/store';

interface LogEntry {
  type: string;
  message: string;
  timestamp: string;
  step?: number;
}

interface FileItem {
  name: string;
  size: number;
  path: string;
}

export default function Home() {
  const [objective, setObjective] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [userMessage, setUserMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  
  const {
    session,
    status,
    modelProvider,
    modelName,
    apiKey,
    ollamaUrl,
    setSession,
    setStatus,
    setModelProvider,
    setModelName,
    setApiKey,
    setOllamaUrl,
    startSession,
    pauseSession,
    resumeSession,
    stopSession,
    sendMessage,
    connectLogs,
    connectScreen,
    disconnect
  } = useAgentStore();

  // Auto-scroll logs
  useEffect(() => {
    const logContainer = document.getElementById('log-container');
    if (logContainer) {
      logContainer.scrollTop = logContainer.scrollHeight;
    }
  }, [logs]);

  // Handle log WebSocket messages
  useEffect(() => {
    if (!session?.session_id) return;

    const handleLogMessage = (data: LogEntry) => {
      setLogs(prev => [...prev, data]);
      
      // Update status based on log type
      if (data.type === 'status_change') {
        if (data.message.includes('paused')) setStatus('paused');
        else if (data.message.includes('resumed')) setStatus('running');
        else if (data.message.includes('stopped')) setStatus('stopped');
        else if (data.message.includes('completed')) setStatus('completed');
      }
    };

    const logWs = connectLogs(handleLogMessage, () => setIsConnected(true));
    
    return () => {
      logWs?.close();
      setIsConnected(false);
    };
  }, [session?.session_id]);

  // Fetch files periodically
  useEffect(() => {
    if (!session?.session_id) return;

    const fetchFiles = async () => {
      try {
        const res = await fetch(`/api/session/${session.session_id}/files`);
        if (res.ok) {
          const data = await res.json();
          setFiles(data.files || []);
        }
      } catch (err) {
        console.error('Failed to fetch files:', err);
      }
    };

    fetchFiles();
    const interval = setInterval(fetchFiles, 5000);
    return () => clearInterval(interval);
  }, [session?.session_id]);

  const handleStart = async () => {
    if (!objective.trim()) return;
    
    setLogs([]);
    setFiles([]);
    
    const result = await startSession({
      objective,
      model_provider: modelProvider,
      model_name: modelName,
      api_key: apiKey || undefined,
      ollama_base_url: ollamaUrl || undefined
    });

    if (result) {
      setStatus('running');
    }
  };

  const handlePause = async () => {
    await pauseSession();
  };

  const handleResume = async () => {
    await resumeSession();
  };

  const handleStop = async () => {
    await stopSession();
    disconnect();
  };

  const handleSendMessage = async () => {
    if (!userMessage.trim() || !session) return;
    
    await sendMessage(userMessage);
    setLogs(prev => [...prev, {
      type: 'user_message',
      message: userMessage,
      timestamp: new Date().toISOString()
    }]);
    setUserMessage('');
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const getLogColor = (type: string) => {
    switch (type) {
      case 'thought': return 'text-blue-400';
      case 'action': return 'text-yellow-400';
      case 'result': return 'text-green-400';
      case 'error': return 'text-red-400';
      case 'user_message': return 'text-purple-400';
      case 'final_answer': return 'text-emerald-400 font-bold';
      default: return 'text-gray-300';
    }
  };

  return (
    <div className="h-screen bg-gray-900 text-white flex flex-col">
      {/* Header */}
      <header className="h-14 border-b border-gray-700 flex items-center justify-between px-4 bg-gray-800">
        <div className="flex items-center gap-2">
          <Monitor className="w-6 h-6 text-blue-400" />
          <h1 className="text-xl font-bold">OpenManus-Web</h1>
          <span className={`ml-2 px-2 py-0.5 rounded text-xs ${
            status === 'running' ? 'bg-green-600' :
            status === 'paused' ? 'bg-yellow-600' :
            status === 'completed' ? 'bg-blue-600' :
            status === 'error' ? 'bg-red-600' :
            'bg-gray-600'
          }`}>
            {status.toUpperCase()}
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          {isConnected && (
            <span className="flex items-center gap-1 text-xs text-green-400">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              Connected
            </span>
          )}
        </div>
      </header>

      {/* Main Content - 3 Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Chat/Logs */}
        <div className="w-96 border-r border-gray-700 flex flex-col bg-gray-800">
          <div className="p-3 border-b border-gray-700 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            <h2 className="font-semibold">Agent Logs</h2>
          </div>
          
          <div id="log-container" className="flex-1 overflow-y-auto p-3 space-y-2 font-mono text-sm">
            {logs.length === 0 ? (
              <div className="text-gray-500 text-center mt-8">
                No logs yet. Start a session to see agent activity.
              </div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className={`border-l-2 border-gray-600 pl-2 py-1 ${getLogColor(log.type)}`}>
                  <div className="text-xs text-gray-500">{formatTime(log.timestamp)}</div>
                  <div>{log.message}</div>
                </div>
              ))
            )}
          </div>

          {/* User Input */}
          <div className="p-3 border-t border-gray-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={userMessage}
                onChange={(e) => setUserMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Send message to agent..."
                className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                disabled={!session}
              />
              <button
                onClick={handleSendMessage}
                disabled={!session || !userMessage.trim()}
                className="p-2 bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Center Panel - Live Screen */}
        <div className="flex-1 flex flex-col bg-gray-900">
          <div className="p-3 border-b border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Monitor className="w-4 h-4" />
              <h2 className="font-semibold">Live Browser View</h2>
            </div>
            {session && (
              <div className="text-xs text-gray-400">
                Session: {session.session_id.slice(0, 8)}...
              </div>
            )}
          </div>
          
          <div className="flex-1 flex items-center justify-center p-4">
            {session ? (
              <ScreenViewer sessionId={session.session_id} />
            ) : (
              <div className="text-gray-500 text-center">
                <Monitor className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>No active session</p>
                <p className="text-sm mt-2">Start a new session to see the browser</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - Controls & Files */}
        <div className="w-80 border-l border-gray-700 flex flex-col bg-gray-800">
          {/* Controls */}
          <div className="p-3 border-b border-gray-700">
            <div className="flex items-center gap-2 mb-4">
              <Settings className="w-4 h-4" />
              <h2 className="font-semibold">Controls</h2>
            </div>

            {!session ? (
              /* Start New Session Form */
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Objective</label>
                  <textarea
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    placeholder="What should the agent do?"
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none"
                    rows={3}
                  />
                </div>

                <div>
                  <label className="block text-xs text-gray-400 mb-1">Model Provider</label>
                  <select
                    value={modelProvider}
                    onChange={(e) => setModelProvider(e.target.value)}
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                  >
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google">Google</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-gray-400 mb-1">Model Name</label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    placeholder={
                      modelProvider === 'ollama' ? 'llama3.1' :
                      modelProvider === 'openai' ? 'gpt-4o' :
                      modelProvider === 'anthropic' ? 'claude-3-5-sonnet-20241022' :
                      'gemini-pro'
                    }
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                  />
                </div>

                {modelProvider !== 'ollama' && (
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">API Key</label>
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="Enter API key"
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                    />
                  </div>
                )}

                {modelProvider === 'ollama' && (
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Ollama URL</label>
                    <input
                      type="text"
                      value={ollamaUrl}
                      onChange={(e) => setOllamaUrl(e.target.value)}
                      placeholder="http://localhost:11434"
                      className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                    />
                  </div>
                )}

                <button
                  onClick={handleStart}
                  disabled={!objective.trim()}
                  className="w-full py-2 bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <Play className="w-4 h-4" />
                  Start Agent
                </button>
              </div>
            ) : (
              /* Session Controls */
              <div className="space-y-2">
                <div className="grid grid-cols-3 gap-2">
                  {status === 'running' ? (
                    <button
                      onClick={handlePause}
                      className="py-2 bg-yellow-600 rounded hover:bg-yellow-700 flex items-center justify-center gap-1 text-sm"
                    >
                      <Pause className="w-4 h-4" />
                      Pause
                    </button>
                  ) : (
                    <button
                      onClick={handleResume}
                      disabled={status !== 'paused'}
                      className="py-2 bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-1 text-sm"
                    >
                      <Play className="w-4 h-4" />
                      Resume
                    </button>
                  )}
                  
                  <button
                    onClick={handleStop}
                    className="py-2 bg-red-600 rounded hover:bg-red-700 flex items-center justify-center gap-1 text-sm col-span-2"
                  >
                    <Square className="w-4 h-4" />
                    Stop Session
                  </button>
                </div>

                <div className="pt-3 border-t border-gray-700">
                  <button
                    onClick={() => {
                      setSession(null);
                      setLogs([]);
                      setStatus('idle');
                    }}
                    className="w-full py-2 bg-gray-600 rounded hover:bg-gray-700 text-sm"
                  >
                    New Session
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Files Panel */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="p-3 border-b border-gray-700 flex items-center gap-2">
              <FileText className="w-4 h-4" />
              <h2 className="font-semibold">Workspace Files</h2>
            </div>
            
            <div className="flex-1 overflow-y-auto p-3">
              {files.length === 0 ? (
                <div className="text-gray-500 text-sm text-center mt-4">
                  No files created yet
                </div>
              ) : (
                <ul className="space-y-1">
                  {files.map((file, index) => (
                    <li
                      key={index}
                      className="text-sm p-2 bg-gray-700 rounded hover:bg-gray-600 cursor-pointer truncate"
                      title={file.path}
                    >
                      {file.name}
                      <span className="text-xs text-gray-400 ml-2">
                        ({Math.round(file.size / 1024)} KB)
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
