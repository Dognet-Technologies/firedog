import React, { useState, useEffect } from 'react';
import auditService, { AuditLog, AuditFilter, AuditStats } from '../services/audit.service';
import './Audit.css';

const Audit: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState<AuditStats | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Filtri
  const [filters, setFilters] = useState<AuditFilter>({
    limit: 100,
  });

  // Dettaglio log selezionato
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [showDetailModal, setShowDetailModal] = useState<boolean>(false);

  useEffect(() => {
    loadLogs();
    loadStats();
  }, []);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await auditService.getAuditLogs(filters);
      setLogs(data.results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await auditService.getStats();
      setStats(data);
    } catch (err: any) {
      console.error('Error loading stats:', err);
    }
  };

  const handleFilterChange = (key: keyof AuditFilter, value: any) => {
    setFilters({ ...filters, [key]: value });
  };

  const applyFilters = () => {
    loadLogs();
  };

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const blob = await auditService.exportLogs(filters);
      
      // Download file
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_logs_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setSuccess('Log esportati con successo');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openDetail = (log: AuditLog) => {
    setSelectedLog(log);
    setShowDetailModal(true);
  };

  const getActionIcon = (action: string): string => {
    if (action.includes('login')) return '🔐';
    if (action.includes('logout')) return '🚪';
    if (action.includes('add') || action.includes('create')) return '➕';
    if (action.includes('delete') || action.includes('remove')) return '🗑️';
    if (action.includes('update') || action.includes('modify')) return '✏️';
    if (action.includes('install')) return '📦';
    if (action.includes('sync')) return '🔄';
    return '📝';
  };

  const getActionColor = (action: string): string => {
    if (action.includes('delete') || action.includes('remove')) return '#ff4d4d';
    if (action.includes('add') || action.includes('create')) return '#7dffaa';
    if (action.includes('login') || action.includes('logout')) return '#00c9ff';
    if (action.includes('update') || action.includes('modify')) return '#ffcc00';
    return '#8e91a1';
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="audit-page">
      {/* Header */}
      <div className="page-header">
        <div className="header-left">
          <h1>Audit Log</h1>
          <p className="subtitle">Registro attività e azioni di sistema</p>
        </div>
        <div className="header-actions">
          <button
            className="btn-export"
            onClick={handleExport}
            disabled={loading}
          >
            📥 Esporta Log
          </button>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="alert alert-error">
          <strong>Errore:</strong> {error}
          <button className="alert-close" onClick={() => setError(null)}>×</button>
        </div>
      )}
      
      {success && (
        <div className="alert alert-success">
          <strong>Successo:</strong> {success}
          <button className="alert-close" onClick={() => setSuccess(null)}>×</button>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_actions}</div>
            <div className="stat-label">Azioni Totali</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.unique_users}</div>
            <div className="stat-label">Utenti Unici</div>
          </div>
          {stats.actions_by_type && Object.keys(stats.actions_by_type).length > 0 && (
            <>
              <div className="stat-card">
                <div className="stat-value">
                  {Object.entries(stats.actions_by_type).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'}
                </div>
                <div className="stat-label">Azione Più Frequente</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {Object.values(stats.actions_by_type).reduce((a, b) => a + b, 0)}
                </div>
                <div className="stat-label">Totale Eventi</div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Filtri */}
      <div className="filters-section">
        <h3>Filtri</h3>
        <div className="filters-grid">
          <div className="filter-group">
            <label>Username</label>
            <input
              type="text"
              placeholder="es. admin"
              value={filters.username || ''}
              onChange={(e) => handleFilterChange('username', e.target.value || undefined)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Azione</label>
            <input
              type="text"
              placeholder="es. target.install"
              value={filters.action || ''}
              onChange={(e) => handleFilterChange('action', e.target.value || undefined)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Target ID</label>
            <input
              type="number"
              placeholder="ID del target"
              value={filters.target_id || ''}
              onChange={(e) => handleFilterChange('target_id', e.target.value ? parseInt(e.target.value) : undefined)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Da Data</label>
            <input
              type="datetime-local"
              value={filters.since || ''}
              onChange={(e) => handleFilterChange('since', e.target.value || undefined)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>A Data</label>
            <input
              type="datetime-local"
              value={filters.until || ''}
              onChange={(e) => handleFilterChange('until', e.target.value || undefined)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Limite Risultati</label>
            <select
              value={filters.limit || 100}
              onChange={(e) => handleFilterChange('limit', parseInt(e.target.value))}
              className="filter-select"
            >
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
              <option value="500">500</option>
            </select>
          </div>
        </div>
        <button className="btn-apply-filters" onClick={applyFilters} disabled={loading}>
          {loading ? 'Caricamento...' : 'Applica Filtri'}
        </button>
      </div>

      {/* Logs Table */}
      <div className="logs-section">
        <h3>Registro Attività</h3>
        {loading && logs.length === 0 ? (
          <div className="loading-spinner">Caricamento log...</div>
        ) : logs.length === 0 ? (
          <div className="no-data">Nessun log trovato</div>
        ) : (
          <div className="table-container">
            <table className="logs-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Username</th>
                  <th>Azione</th>
                  <th>Target</th>
                  <th>IP Address</th>
                  <th>Dettagli</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="timestamp-cell">{formatDate(log.timestamp)}</td>
                    <td>
                      <span className="username-badge">{log.username}</span>
                    </td>
                    <td>
                      <span
                        className="action-badge"
                        style={{
                          background: `${getActionColor(log.action)}33`,
                          color: getActionColor(log.action),
                          border: `1px solid ${getActionColor(log.action)}66`
                        }}
                      >
                        {getActionIcon(log.action)} {log.action}
                      </span>
                    </td>
                    <td className="target-cell">
                      {log.target ? (
                        <>
                          <div className="target-hostname">{log.target.hostname}</div>
                          <div className="target-ip">{log.target.ip_address}</div>
                        </>
                      ) : (
                        <span className="no-target">-</span>
                      )}
                    </td>
                    <td className="ip-cell">{log.ip_address || '-'}</td>
                    <td>
                      <button
                        className="btn-detail"
                        onClick={() => openDetail(log)}
                      >
                        Vedi
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {showDetailModal && selectedLog && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Dettagli Log Audit</h3>
              <button className="modal-close" onClick={() => setShowDetailModal(false)}>×</button>
            </div>
            
            <div className="detail-body">
              <div className="detail-row">
                <span className="detail-label">ID:</span>
                <span className="detail-value">{selectedLog.id}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Timestamp:</span>
                <span className="detail-value">{formatDate(selectedLog.timestamp)}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Username:</span>
                <span className="detail-value username-value">{selectedLog.username}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Azione:</span>
                <span
                  className="action-badge"
                  style={{
                    background: `${getActionColor(selectedLog.action)}33`,
                    color: getActionColor(selectedLog.action),
                    border: `1px solid ${getActionColor(selectedLog.action)}66`
                  }}
                >
                  {getActionIcon(selectedLog.action)} {selectedLog.action}
                </span>
              </div>

              {selectedLog.target && (
                <>
                  <div className="detail-row">
                    <span className="detail-label">Target Hostname:</span>
                    <span className="detail-value">{selectedLog.target.hostname}</span>
                  </div>

                  <div className="detail-row">
                    <span className="detail-label">Target IP:</span>
                    <span className="detail-value ip-value">{selectedLog.target.ip_address}</span>
                  </div>
                </>
              )}

              <div className="detail-row">
                <span className="detail-label">IP Address:</span>
                <span className="detail-value ip-value">{selectedLog.ip_address || 'N/A'}</span>
              </div>

              {selectedLog.details && Object.keys(selectedLog.details).length > 0 && (
                <div className="detail-row full-width">
                  <span className="detail-label">Dettagli JSON:</span>
                  <pre className="json-details">
                    {JSON.stringify(selectedLog.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowDetailModal(false)}
              >
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Audit;
