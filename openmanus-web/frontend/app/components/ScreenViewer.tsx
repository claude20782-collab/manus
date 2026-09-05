'use client';

import { useEffect, useRef, useState } from 'react';

interface ScreenViewerProps {
  sessionId: string;
}

export default function ScreenViewer({ sessionId }: ScreenViewerProps) {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
    type: string;
  } | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());

  useEffect(() => {
    // Get WebSocket URL from environment or default
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = process.env.NEXT_PUBLIC_WS_URL || `${wsProtocol}//${window.location.host}`;
    const wsUrl = `${wsHost}/ws/session/${sessionId}/screen`;

    // Connect to screen WebSocket
    wsRef.current = new WebSocket(wsUrl);
    wsRef.current.binaryType = 'arraybuffer';

    wsRef.current.onopen = () => {
      console.log('Screen WebSocket connected');
    };

    wsRef.current.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Convert binary data to base64 image
        const blob = new Blob([event.data], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        
        // Revoke previous URL to avoid memory leak
        if (imageSrc) {
          URL.revokeObjectURL(imageSrc);
        }
        
        setImageSrc(url);
        
        // Track FPS
        frameCountRef.current++;
        const now = Date.now();
        if (now - lastFpsUpdateRef.current >= 1000) {
          setFps(frameCountRef.current);
          frameCountRef.current = 0;
          lastFpsUpdateRef.current = now;
        }
      }
    };

    wsRef.current.onerror = (error) => {
      console.error('Screen WebSocket error:', error);
    };

    wsRef.current.onclose = () => {
      console.log('Screen WebSocket closed');
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (imageSrc) {
        URL.revokeObjectURL(imageSrc);
      }
    };
  }, [sessionId]);

  // Clean up object URLs when component unmounts or image changes
  useEffect(() => {
    return () => {
      if (imageSrc) {
        URL.revokeObjectURL(imageSrc);
      }
    };
  }, [imageSrc]);

  return (
    <div className="relative w-full h-full flex items-center justify-center bg-gray-800 rounded-lg overflow-hidden">
      {imageSrc ? (
        <>
          <img
            ref={imgRef}
            src={imageSrc}
            alt="Live browser screen"
            className="max-w-full max-h-full object-contain"
            style={{
              imageRendering: 'auto'
            }}
          />
          
          {/* Action Overlay - Shows where agent is clicking/typing */}
          {overlay && (
            <div
              className="absolute border-2 border-red-500 bg-red-500/20 pointer-events-none animate-pulse"
              style={{
                left: overlay.x,
                top: overlay.y,
                width: overlay.width,
                height: overlay.height,
              }}
            >
              <div className="absolute -top-6 left-0 bg-red-500 text-white text-xs px-2 py-0.5 rounded whitespace-nowrap">
                {overlay.type}
              </div>
            </div>
          )}

          {/* FPS Counter */}
          <div className="absolute top-2 right-2 bg-black/70 text-green-400 text-xs px-2 py-1 rounded font-mono">
            {fps} FPS
          </div>

          {/* Connection Status */}
          <div className="absolute bottom-2 right-2 flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-gray-300">Live</span>
          </div>
        </>
      ) : (
        <div className="text-gray-500 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full mx-auto mb-4" />
          <p>Waiting for screen stream...</p>
          <p className="text-xs mt-2">Session ID: {sessionId.slice(0, 8)}...</p>
        </div>
      )}
    </div>
  );
}
