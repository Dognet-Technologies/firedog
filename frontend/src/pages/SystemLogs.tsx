/**
 * System Logs Page
 * Visualizza log di sistema dai target remoti
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target } from '../types';
import './SystemLogs.css';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  service: string;
  message: string;
}

type LogType = 'syslog' | 'auth' | 'kern' | 'apache' | 'nginx';

const SystemLogs: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);
  const [selectedLogType, setSelectedLogType] = useState<LogType>('syslog');
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState({
    level: '',
    search: '',
    lines: 100,
  });
  const [autoRefresh, setAutoRefresh] = useState(false);

  const logTypeConfig = {
    syslog: { 
      label: 'System Log', 
      path: '/var/log/syslog',
      icon: '📋',
      description: 'Log di sistema generale' 
    },
    auth: { 
      label: 'Authentication', 
      path: '/var/log/auth.log',
      icon: '🔐',
      description: 'Log di autenticazione SSH/sudo' 
    },
    kern: { 
      label: 'Kernel Log', 
      path: '/var/log/kern.log',
      icon: '⚙️',
      description: 'Log del kernel Linux' 
    },
    apache: { 
      label: 'Apache', 
      path: '/var/log/apache2/error.log',
      icon: '🌐',
      description: 'Log errori Apache' 
    },
    nginx: { 
      label: 'Nginx', 
      path: '/var/log/nginx/error.log',
      icon: '🚀',
      description: 'Log errori Nginx' 
    },
  };

  const levelConfig = {
    info: { color: 'info', icon: 'ℹ️' },
    warning: { color: 'warning', icon: '⚠️' },
    error: { color: 'danger', icon: '❌' },
    debug: { color: 'default', icon: '🔍' },
  };

  useEffect(() => {
    loadTargets();
  }, []);

  useEffect(() => {
    if (selectedTarget) {
      loadLogs();
    }
  }, [selectedTarget, selectedLogType, filter.lines]);

  useEffect(() => {
    if (autoRefresh && selectedTarget) {
      const interval = setInterval(loadLogs, 10000); // Refresh every 10s
      return () => clearInterval(interval);
    }
  }, [autoRefresh, selectedTarget, selectedLogType]);

  const loadTargets = async () => {
    try {
      const response = await apiService.getTargets();
      setTargets(response.results.filter(t => t.status === 'online'));
      if (response.results.length > 0) {
        setSelectedTarget(response.results[0].id);
      }
    } catch (error) {
      console.error('Error loading targets:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async () => {
    if (!selectedTarget) return;

    try {
      setLoading(true);

      // TODO: Implementare API backend reale per recuperare log via SSH
      // API call would go here when backend is ready
      // For now, data remains empty

    } catch (error) {
      console.error('Error loading system logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    const content = logs.map(log => 
      `[${log.timestamp}] [${log.level.toUpperCase()}] ${log.service}: ${log.message}`
    ).join('\n');
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedLogType}_${new Date().toISOString().split('T')[0]}.log`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const filteredLogs = logs.filter(log => {
    if (filter.level && log.level !== filter.level) return false;
    if (filter.search && !log.message.toLowerCase().includes(filter.search.toLowerCase())) return false;
    return true;
  });

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return new Intl.DateTimeFormat('it-IT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  };

  return (
    <div className="system-logs-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            System Logs
          </h1>
          <p>Log di sistema dai target remoti</p>
        </div>
      </div>

      {/* Controls */}
      <div className="controls-section">
        <div className="control-row">
          <div className="control-group">
            <label>Target</label>
            <select
              value={selectedTarget || ''}
              onChange={(e) => setSelectedTarget(Number(e.target.value))}
              disabled={loading}
            >
              <option value="">Seleziona un target</option>
              {targets.map((target) => (
                <option key={target.id} value={target.id}>
                  {target.hostname} ({target.ip_address})
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label>Tipo Log</label>
            <select
              value={selectedLogType}
              onChange={(e) => setSelectedLogType(e.target.value as LogType)}
              disabled={loading}
            >
              {Object.entries(logTypeConfig).map(([key, config]) => (
                <option key={key} value={key}>
                  {config.icon} {config.label}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label>Linee</label>
            <select
              value={filter.lines}
              onChange={(e) => setFilter({ ...filter, lines: Number(e.target.value) })}
              disabled={loading}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
          </div>
        </div>

        <div className="control-row">
          <div className="control-group">
            <label>Livello</label>
            <select
              value={filter.level}
              onChange={(e) => setFilter({ ...filter, level: e.target.value })}
            >
              <option value="">Tutti i livelli</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="debug">Debug</option>
            </select>
          </div>

          <div className="control-group search-group">
            <label>Cerca</label>
            <input
              type="text"
              placeholder="Filtra per contenuto..."
              value={filter.search}
              onChange={(e) => setFilter({ ...filter, search: e.target.value })}
            />
          </div>

          <div className="control-actions">
            <button
              className={`btn-toggle ${autoRefresh ? 'active' : ''}`}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"></path>
              </svg>
              Auto-refresh {autoRefresh && <span className="pulse-dot-small"></span>}
            </button>

            <button className="btn-action" onClick={loadLogs} disabled={loading}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"></path>
              </svg>
              Ricarica
            </button>

            <button className="btn-action" onClick={handleDownload} disabled={logs.length === 0}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"></path>
              </svg>
              Download
            </button>
          </div>
        </div>
      </div>

      {/* Log Type Info */}
      {selectedLogType && (
        <div className="log-type-info">
          <span className="log-icon">{logTypeConfig[selectedLogType].icon}</span>
          <div className="log-info-content">
            <strong>{logTypeConfig[selectedLogType].label}</strong>
            <span>{logTypeConfig[selectedLogType].description}</span>
            <code>{logTypeConfig[selectedLogType].path}</code>
          </div>
          <div className="log-count">
            {filteredLogs.length} / {logs.length} righe
          </div>
        </div>
      )}

      {/* Logs Display */}
      <div className="logs-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento log...</p>
          </div>
        ) : !selectedTarget ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <h3>Seleziona un Target</h3>
            <p>Scegli un target online per visualizzare i suoi log di sistema</p>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <h3>Nessun Log Trovato</h3>
            <p>Prova a modificare i filtri di ricerca</p>
          </div>
        ) : (
          <div className="logs-viewer">
            {filteredLogs.map((log, idx) => (
              <div key={idx} className={`log-line level-${log.level}`}>
                <span className="log-timestamp">{formatTimestamp(log.timestamp)}</span>
                <span className={`log-level level-${log.level}`}>
                  <span className="level-icon">{levelConfig[log.level].icon}</span>
                  {log.level.toUpperCase()}
                </span>
                <span className="log-service">{log.service}</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemLogs;
