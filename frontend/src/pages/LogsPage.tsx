/**
 * Logs Page - Real-time Application Logs
 * Visualizza log di Django, Celery Worker, Celery Beat in tempo reale
 */
import React, { useEffect, useState, useRef } from 'react';
import logService, { LogEntry, LogSource } from '../services/logs.service';
import './LogsPage.css';

const LogsPage: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [sources, setSources] = useState<LogSource[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [selectedLevel, setSelectedLevel] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  // Carica sorgenti log disponibili
  useEffect(() => {
    loadSources();
  }, []);

  // Connetti WebSocket
  useEffect(() => {
    logService.connect(
      (entry: LogEntry) => {
        if (entry.type === 'connection') {
          setIsConnected(true);
          return;
        }

        if (entry.type === 'clear') {
          setLogs([]);
          return;
        }

        setLogs((prev) => [...prev, entry]);
      },
      (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      }
    );

    return () => {
      logService.disconnect();
    };
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const loadSources = async () => {
    try {
      const data = await logService.getSources();
      setSources(data);
    } catch (error) {
      console.error('Error loading sources:', error);
    }
  };

  const handlePauseResume = () => {
    if (isPaused) {
      logService.sendCommand('resume');
    } else {
      logService.sendCommand('pause');
    }
    setIsPaused(!isPaused);
  };

  const handleClear = () => {
    setLogs([]);
  };

  const handleLoadHistory = async () => {
    try {
      const history = await logService.getHistory(
        selectedSource === 'all' ? 'django' : selectedSource,
        500
      );
      
      const historyEntries: LogEntry[] = history.map((line) => ({
        type: 'log',
        source: selectedSource === 'all' ? 'django' : (selectedSource as any),
        message: line,
        timestamp: null,
      }));

      setLogs(historyEntries);
    } catch (error) {
      console.error('Error loading history:', error);
    }
  };

  // Filtra log in base ai filtri attivi
  const filteredLogs = logs.filter((log) => {
    // Filtro sorgente
    if (selectedSource !== 'all' && log.source !== selectedSource) {
      return false;
    }

    // Filtro livello
    if (selectedLevel !== 'all') {
      const levelMatch = log.message.match(/\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b/);
      const logLevel = levelMatch ? levelMatch[1] : 'INFO';
      if (logLevel !== selectedLevel) {
        return false;
      }
    }

    // Filtro ricerca testuale
    if (searchTerm && !log.message.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }

    return true;
  });

  const getLogLevel = (message: string): string => {
    const match = message.match(/\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b/);
    return match ? match[1] : 'INFO';
  };

  const getLogLevelClass = (level: string): string => {
    switch (level) {
      case 'DEBUG':
        return 'log-debug';
      case 'INFO':
        return 'log-info';
      case 'WARNING':
        return 'log-warning';
      case 'ERROR':
        return 'log-error';
      case 'CRITICAL':
        return 'log-critical';
      default:
        return 'log-info';
    }
  };

  const getSourceIcon = (source?: string): string => {
    switch (source) {
      case 'django':
        return '🌐';
      case 'celery':
        return '⚙️';
      case 'application':
        return '📱';
      default:
        return '📝';
    }
  };

  return (
    <div className="logs-page">
      {/* Header */}
      <div className="logs-header">
        <div className="header-left">
          <h1>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
            </svg>
            Application Logs
          </h1>
          <p>Log in tempo reale dell'applicazione FireDog</p>
        </div>

        <div className="header-status">
          <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            {isConnected ? 'Connesso' : 'Disconnesso'}
          </div>
        </div>
      </div>

      {/* Filters & Controls */}
      <div className="logs-controls">
        <div className="controls-left">
          <div className="control-group">
            <label>Sorgente</label>
            <select value={selectedSource} onChange={(e) => setSelectedSource(e.target.value)}>
              <option value="all">Tutte</option>
              <option value="django">Django/Daphne</option>
              <option value="celery">Celery</option>
              <option value="application">Application</option>
            </select>
          </div>

          <div className="control-group">
            <label>Livello</label>
            <select value={selectedLevel} onChange={(e) => setSelectedLevel(e.target.value)}>
              <option value="all">Tutti</option>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>

          <div className="control-group search-group">
            <label>Ricerca</label>
            <input
              type="text"
              placeholder="Cerca nei log..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="controls-right">
          <button className="btn-control" onClick={handleLoadHistory} title="Carica storico">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
            </svg>
            Storico
          </button>

          <button
            className={`btn-control ${isPaused ? 'paused' : ''}`}
            onClick={handlePauseResume}
            title={isPaused ? 'Resume' : 'Pause'}
          >
            {isPaused ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
            )}
            {isPaused ? 'Resume' : 'Pause'}
          </button>

          <button className="btn-control" onClick={handleClear} title="Pulisci log">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            Pulisci
          </button>

          <label className="auto-scroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            <span>Auto-scroll</span>
          </label>
        </div>
      </div>

      {/* Log Sources Info */}
      {sources.length > 0 && (
        <div className="sources-info">
          {sources.map((source) => (
            <div key={source.key} className={`source-card ${!source.exists ? 'disabled' : ''}`}>
              <div className="source-icon">{getSourceIcon(source.key)}</div>
              <div className="source-details">
                <div className="source-name">{source.name}</div>
                <div className="source-size">{source.size_human}</div>
              </div>
              {!source.exists && <div className="source-badge">Non disponibile</div>}
            </div>
          ))}
        </div>
      )}

      {/* Logs Display */}
      <div className="logs-container" ref={logsContainerRef}>
        <div className="logs-content">
          {filteredLogs.length === 0 ? (
            <div className="no-logs">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
              </svg>
              <p>Nessun log da visualizzare</p>
            </div>
          ) : (
            filteredLogs.map((log, index) => {
              const level = getLogLevel(log.message);
              return (
                <div key={index} className={`log-entry ${getLogLevelClass(level)}`}>
                  <span className="log-source" title={log.source}>
                    {getSourceIcon(log.source)}
                  </span>
                  <span className="log-level">{level}</span>
                  <span className="log-message">{log.message}</span>
                </div>
              );
            })
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Footer Stats */}
      <div className="logs-footer">
        <div className="footer-stats">
          <span>Totale log: <strong>{logs.length}</strong></span>
          <span className="separator">•</span>
          <span>Visualizzati: <strong>{filteredLogs.length}</strong></span>
          <span className="separator">•</span>
          <span className={isPaused ? 'paused-indicator' : ''}>
            {isPaused ? '⏸ Paused' : '▶ Live'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default LogsPage;
