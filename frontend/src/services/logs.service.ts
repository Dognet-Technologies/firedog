/**
 * Log Service
 * Gestisce connessione WebSocket e API per log streaming
 */

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

function buildWsUrl(path: string): string {
  // In produzione passa dal reverse proxy nginx (stesso host, schema ws/wss
  // derivato da http/https). In dev fallback a localhost:8000.
  if (typeof window !== 'undefined' && window.location && window.location.host) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
  }
  return `ws://localhost:8000${path}`;
}

export interface LogEntry {
  type: 'log' | 'error' | 'connection' | 'clear';
  source?: 'django' | 'celery' | 'application';
  message: string;
  timestamp?: string | null;
}

export interface LogSource {
  key: string;
  name: string;
  description: string;
  exists: boolean;
  size: number;
  size_human: string;
}

class LogService {
  private ws: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private listeners: ((entry: LogEntry) => void)[] = [];

  /**
   * Connetti al WebSocket per log streaming
   */

  connect(onMessage: (entry: LogEntry) => void, onError?: (error: Event) => void) {
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.error('No auth token found');
      return;
    }

    // Aggiungi listener
    this.listeners.push(onMessage);

    // WebSocket URL con token nell'URL (Django Channels non supporta headers custom)
    const wsUrl = `${buildWsUrl('/ws/logs/stream/')}?token=${token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const data: LogEntry = JSON.parse(event.data);
        // Notifica tutti i listener
        this.listeners.forEach(listener => listener(data));
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (onError) onError(error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed, attempting reconnect...');
      // Auto-reconnect dopo 3 secondi
      this.reconnectTimeout = setTimeout(() => {
        this.connect(onMessage, onError);
      }, 3000);
    };
  }
  /**
   * Disconnetti WebSocket
   */
  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.listeners = [];
  }

  /**
   * Invia comando (pause/resume/clear)
   */
  sendCommand(command: 'pause' | 'resume' | 'clear') {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command }));
    }
  }

  /**
   * Recupera storico log via REST API
   */
  async getHistory(source: string = 'django', lines: number = 100): Promise<string[]> {
    const token = localStorage.getItem('access_token');
    const response = await fetch(
      `${API_URL}/logs/?source=${source}&lines=${lines}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error('Failed to fetch log history');
    }

    const data = await response.json();
    return data.logs || [];
  }

  /**
   * Recupera elenco sorgenti log disponibili
   */
  async getSources(): Promise<LogSource[]> {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_URL}/logs/sources/`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch log sources');
    }

    const data = await response.json();
    return data.sources || [];
  }
}

export default new LogService();
