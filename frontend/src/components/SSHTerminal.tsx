/**
 * SSH Terminal Component
 * Terminale interattivo per installazione FireDog sui target
 */
import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import './SSHTerminal.css';

interface SSHTerminalProps {
  targetId: number;
  onClose: () => void;
  onInstallComplete?: () => void;
}

const SSHTerminal: React.FC<SSHTerminalProps> = ({ targetId, onClose, onInstallComplete }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const [terminal, setTerminal] = useState<Terminal | null>(null);
  const [fitAddon, setFitAddon] = useState<FitAddon | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const isMountedRef = useRef(true);

  // Inizializza terminale xterm.js
  useEffect(() => {
    if (!terminalRef.current) return;

    isMountedRef.current = true;

    // Crea istanza terminale
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: '"Cascadia Code", "Fira Code", "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
        cursorAccent: '#000000',
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5',
      },
      rows: 24,
      cols: 80,
    });

    // Addon per auto-fit dimensioni terminale
    const fit = new FitAddon();
    term.loadAddon(fit);

    // Monta terminale nel DOM
    term.open(terminalRef.current);

    // Aspetta che il renderer sia completamente inizializzato
    // Usa un approccio con retry per garantire che xterm sia pronto
    let fitTimer: NodeJS.Timeout | null = null;
    let attempts = 0;
    const maxAttempts = 20; // Max 2 secondi (20 * 100ms)

    const tryFit = () => {
      if (!isMountedRef.current || !terminalRef.current) return;

      attempts++;

      try {
        // Verifica che TUTTO sia inizializzato: renderer, viewport, e dimensions
        const core = (term as any)._core;
        const hasRenderer = core?._renderService?._renderer?.value;
        const hasViewport = core?.viewport;

        if (hasRenderer && hasViewport) {
          // Tutto pronto, possiamo fare fit
          fit.fit();
        } else if (attempts < maxAttempts) {
          // Non ancora pronto, riprova
          fitTimer = setTimeout(tryFit, 100);
        }
        // Altrimenti abbandona silenziosamente (terminale non si è inizializzato in tempo)
      } catch (e) {
        // Se fallisce e non abbiamo superato i tentativi, riprova
        if (attempts < maxAttempts) {
          fitTimer = setTimeout(tryFit, 100);
        }
      }
    };

    // Inizia a provare dopo che il DOM è stato aggiornato
    requestAnimationFrame(() => {
      fitTimer = setTimeout(tryFit, 100);
    });

    setTerminal(term);
    setFitAddon(fit);

    // Cleanup
    return () => {
      if (fitTimer) clearTimeout(fitTimer);
      isMountedRef.current = false;
      // Dispose terminale in modo sicuro
      try {
        term.dispose();
      } catch (e) {
        // Ignora errori durante cleanup
      }
    };
  }, []);

  // Gestione ridimensionamento finestra
  useEffect(() => {
    if (!fitAddon || !terminal || !ws || !isConnected) return;

    const handleResize = () => {
      if (!isMountedRef.current) return;

      setTimeout(() => {
        if (!isMountedRef.current || !terminalRef.current) return;

        try {
          // Verifica che il renderer E viewport esistano prima di chiamare fit()
          const core = (terminal as any)._core;
          const hasRenderer = core?._renderService?._renderer?.value;
          const hasViewport = core?.viewport;

          if (hasRenderer && hasViewport && fitAddon) {
            fitAddon.fit();

            // Invia nuovo dimensionamento al backend
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({
                type: 'resize',
                width: terminal.cols,
                height: terminal.rows
              }));
            }
          }
        } catch (e) {
          // Ignora silenziosamente errori di resize
        }
      }, 50);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [fitAddon, terminal, ws, isConnected]);

  // Connessione WebSocket
  useEffect(() => {
    if (!terminal) return;

    // Connessione WebSocket al BACKEND (Django su porta 8000)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // CORREZIONE: usa localhost:8000 invece di window.location.host
    const wsUrl = `${protocol}//localhost:8000/ws/terminal/`;

    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      console.log('WebSocket connesso');
      
      // Invia richiesta connessione SSH al target
      websocket.send(JSON.stringify({
        type: 'connect',
        target_id: targetId,
        width: terminal.cols,
        height: terminal.rows
      }));
    };

    websocket.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'connected':
          setIsConnected(true);
          setIsConnecting(false);
          terminal.writeln(`\r\n\x1b[32m✓ ${message.message}\x1b[0m\r\n`);
          break;

        case 'output':
          // Scrivi output dal server SSH nel terminale
          terminal.write(message.data);
          break;

        case 'error':
          terminal.writeln(`\r\n\x1b[31m✗ Error: ${message.message}\x1b[0m\r\n`);
          setIsConnecting(false);
          break;

        case 'disconnected':
          terminal.writeln(`\r\n\x1b[33m⚠ ${message.message}\x1b[0m\r\n`);
          setIsConnected(false);
          
          // Notifica parent se installazione completata
          if (onInstallComplete) {
            onInstallComplete();
          }
          break;

        default:
          console.warn('Tipo messaggio sconosciuto:', message.type);
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      terminal.writeln('\r\n\x1b[31m✗ Errore connessione WebSocket\x1b[0m\r\n');
      setIsConnecting(false);
    };

    websocket.onclose = () => {
      console.log('WebSocket chiuso');
      setIsConnected(false);
      setIsConnecting(false);
    };

    setWs(websocket);

    // Gestione input utente
    const handleData = terminal.onData((data) => {
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
          type: 'input',
          data: data
        }));
      }
    });

    // Cleanup
    return () => {
      handleData.dispose();
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({ type: 'disconnect' }));
        websocket.close();
      }
    };
  }, [terminal, targetId]);

  const handleClose = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'disconnect' }));
      ws.close();
    }
    onClose();
  };

  return (
    <div className="ssh-terminal-modal">
      <div className="terminal-header">
        <h3>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M7 7l5 5-5 5M13 17h5" />
          </svg>
          SSH Terminal - Target #{targetId}
        </h3>
        <div className="terminal-status">
          {isConnecting && (
            <span className="status-connecting">
              <span className="spinner-small"></span> Connessione...
            </span>
          )}
          {isConnected && (
            <span className="status-connected">
              <span className="pulse-dot"></span> Connesso
            </span>
          )}
          {!isConnecting && !isConnected && (
            <span className="status-disconnected">Disconnesso</span>
          )}
        </div>
        <button className="terminal-close" onClick={handleClose} title="Chiudi terminale">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="terminal-container">
        <div ref={terminalRef} className="terminal-wrapper" />
      </div>
      <div className="terminal-footer">
        <span className="terminal-hint">
          💡 Tip: Inserisci la password sudo quando richiesta per completare l'installazione
        </span>
      </div>
    </div>
  );
};

export default SSHTerminal;
