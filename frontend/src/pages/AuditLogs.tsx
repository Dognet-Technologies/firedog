/**
 * Audit Logs Page
 * Visualizza log delle azioni amministrative con filtri avanzati
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import './AuditLogs.css';

interface AuditLog {
  id: number;
  username: string;
  action: string;
  target_id: number | null;
  target_hostname: string | null;
  details: any;
  ip_address: string;
  timestamp: string;
  action_description: string;
}

interface PaginatedResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: AuditLog[];
}

const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    count: 0,
    next: null as string | null,
    previous: null as string | null,
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState({
    username: '',
    action: '',
    target: '',
    search: '',
  });

  // Action icons mapping
  const actionIcons: { [key: string]: string } = {
    login: '🔐',
    logout: '🚪',
    'target.add': '➕',
    'target.install': '📦',
    'target.delete': '🗑️',
    'rule.add': '✅',
    'rule.remove': '❌',
    'threat.acknowledge': '✓',
    'config.update': '⚙️',
    'ssh_key.rotate': '🔑',
    'file.integrity.violation': '⚠️',
    'traffic.analyze': '📊',
  };

  // Action colors
  const actionColors: { [key: string]: string } = {
    login: 'success',
    logout: 'info',
    'target.add': 'success',
    'target.install': 'info',
    'target.delete': 'danger',
    'rule.add': 'success',
    'rule.remove': 'warning',
    'threat.acknowledge': 'info',
    'config.update': 'warning',
    'ssh_key.rotate': 'warning',
    'file.integrity.violation': 'danger',
    'traffic.analyze': 'info',
  };

  useEffect(() => {
    loadLogs();
  }, [currentPage, filters]);

  const loadLogs = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: currentPage,
      };

      if (filters.username) params.username = filters.username;
      if (filters.action) params.action = filters.action;
      if (filters.target) params.target = filters.target;

      const response: PaginatedResponse = await apiService.getAuditLogs(params);
      
      setLogs(response.results);
      setPagination({
        count: response.count,
        next: response.next,
        previous: response.previous,
      });
    } catch (error) {
      console.error('Error loading audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1); // Reset to first page on filter change
  };

  const handleClearFilters = () => {
    setFilters({
      username: '',
      action: '',
      target: '',
      search: '',
    });
    setCurrentPage(1);
  };

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

  const getActionIcon = (action: string) => {
    return actionIcons[action] || '📝';
  };

  const getActionColor = (action: string) => {
    return actionColors[action] || 'default';
  };

  const renderDetails = (details: any) => {
    if (!details || Object.keys(details).length === 0) {
      return <span className="no-details">No additional details</span>;
    }

    return (
      <div className="log-details">
        {Object.entries(details).map(([key, value]) => (
          <div key={key} className="detail-item">
            <span className="detail-key">{key}:</span>
            <span className="detail-value">
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  const totalPages = Math.ceil(pagination.count / 20); // Assuming 20 items per page

  return (
    <div className="audit-logs-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
            Audit Logs
          </h1>
          <p>Registro completo delle azioni amministrative</p>
        </div>
        <div className="header-stats">
          <div className="stat">
            <span className="stat-label">Totale Log</span>
            <span className="stat-value">{pagination.count.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-section">
        <div className="filters-grid">
          <div className="filter-group">
            <label>Username</label>
            <input
              type="text"
              placeholder="Filtra per utente..."
              value={filters.username}
              onChange={(e) => handleFilterChange('username', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Azione</label>
            <select
              value={filters.action}
              onChange={(e) => handleFilterChange('action', e.target.value)}
            >
              <option value="">Tutte le azioni</option>
              <option value="login">Login</option>
              <option value="logout">Logout</option>
              <option value="target.add">Target Add</option>
              <option value="target.install">Target Install</option>
              <option value="target.delete">Target Delete</option>
              <option value="rule.add">Rule Add</option>
              <option value="rule.remove">Rule Remove</option>
              <option value="threat.acknowledge">Threat Acknowledge</option>
              <option value="config.update">Config Update</option>
              <option value="ssh_key.rotate">SSH Key Rotate</option>
              <option value="file.integrity.violation">File Integrity Violation</option>
              <option value="traffic.analyze">Traffic Analyze</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Target ID</label>
            <input
              type="text"
              placeholder="Filtra per target..."
              value={filters.target}
              onChange={(e) => handleFilterChange('target', e.target.value)}
            />
          </div>

          <div className="filter-actions">
            <button className="btn-clear" onClick={handleClearFilters}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
              Cancella Filtri
            </button>
            <button className="btn-refresh" onClick={loadLogs}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
              </svg>
              Aggiorna
            </button>
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="logs-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento log...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
            </svg>
            <h3>Nessun log trovato</h3>
            <p>Prova a modificare i filtri di ricerca</p>
          </div>
        ) : (
          <div className="logs-table-wrapper">
            <table className="logs-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Utente</th>
                  <th>Azione</th>
                  <th>Target</th>
                  <th>IP Address</th>
                  <th>Dettagli</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="log-row">
                    <td className="timestamp-cell">
                      {formatTimestamp(log.timestamp)}
                    </td>
                    <td className="username-cell">
                      <div className="user-info">
                        <div className="user-avatar">
                          {log.username.charAt(0).toUpperCase()}
                        </div>
                        <span>{log.username}</span>
                      </div>
                    </td>
                    <td className="action-cell">
                      <span className={`action-badge action-${getActionColor(log.action)}`}>
                        <span className="action-icon">{getActionIcon(log.action)}</span>
                        <span className="action-text">{log.action_description}</span>
                      </span>
                    </td>
                    <td className="target-cell">
                      {log.target_hostname ? (
                        <span className="target-info">
                          <span className="target-name">{log.target_hostname}</span>
                          <span className="target-id">#{log.target_id}</span>
                        </span>
                      ) : (
                        <span className="no-target">—</span>
                      )}
                    </td>
                    <td className="ip-cell">
                      <code>{log.ip_address || '—'}</code>
                    </td>
                    <td className="details-cell">
                      {renderDetails(log.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {!loading && logs.length > 0 && (
        <div className="pagination">
          <button
            className="pagination-btn"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={!pagination.previous}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M15 19l-7-7 7-7" />
            </svg>
            Precedente
          </button>

          <div className="pagination-info">
            Pagina <strong>{currentPage}</strong> di <strong>{totalPages}</strong>
            <span className="separator">•</span>
            <strong>{pagination.count}</strong> log totali
          </div>

          <button
            className="pagination-btn"
            onClick={() => setCurrentPage((p) => p + 1)}
            disabled={!pagination.next}
          >
            Successiva
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
};

export default AuditLogs;
