/**
 * Firewall Logs Page
 * Visualizza log dei pacchetti droppati dal firewall e minacce rilevate
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import type { ThreatLog } from '../types';
import { useNotifications } from '../contexts/NotificationContext';
import './FirewallLogs.css';

interface FilterState {
  target: string;
  severity: string;
  source_ip: string;
  protocol: string;
  dateRange: 'today' | '7days' | '30days' | 'all';
}

const FirewallLogs: React.FC = () => {
  const navigate = useNavigate();
  const { showToast, showConfirm } = useNotifications();
  const [threats, setThreats] = useState<ThreatLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    count: 0,
    next: null as string | null,
    previous: null as string | null,
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState<FilterState>({
    target: '',
    severity: '',
    source_ip: '',
    protocol: '',
    dateRange: '7days',
  });

  // Severity icons and colors
  const severityConfig = {
    critical: { icon: '🔴', label: 'Critical', color: 'danger' },
    high: { icon: '🟠', label: 'High', color: 'warning' },
    medium: { icon: '🟡', label: 'Medium', color: 'info' },
    low: { icon: '🟢', label: 'Low', color: 'success' },
  };

  useEffect(() => {
    loadThreats();
  }, [currentPage, filters]);

  const loadThreats = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: currentPage,
      };

      if (filters.target) params.target = filters.target;
      if (filters.severity) params.severity = filters.severity;
      if (filters.source_ip) params.source_ip = filters.source_ip;
      if (filters.protocol) params.protocol = filters.protocol;

      const response = await apiService.getThreats(params);
      setThreats(response.results);
      setPagination({
        count: response.count,
        next: response.next,
        previous: response.previous,
      });
    } catch (error) {
      console.error('Error loading firewall logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: keyof FilterState, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setFilters({
      target: '',
      severity: '',
      source_ip: '',
      protocol: '',
      dateRange: '7days',
    });
    setCurrentPage(1);
  };

  const handleResolve = async (threatId: number) => {
    showConfirm({
      title: 'Conferma Risoluzione',
      message: 'Vuoi marcare questa minaccia come risolta?',
      confirmText: 'Risolvi',
      cancelText: 'Annulla',
      onConfirm: async () => {
        try {
          await apiService.markThreatResolved(threatId);
          showToast({
            type: 'success',
            title: 'Minaccia risolta',
            message: 'La minaccia è stata marcata come risolta'
          });
          loadThreats();
        } catch (error) {
          console.error('Error resolving threat:', error);
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile risolvere la minaccia'
          });
        }
      }
    });
  };

  const handleBlock = async (threatId: number) => {
    showConfirm({
      title: 'Conferma Blocco IP',
      message: 'Vuoi bloccare permanentemente questo IP? L\'operazione è irreversibile.',
      confirmText: 'Blocca',
      cancelText: 'Annulla',
      type: 'danger',
      onConfirm: async () => {
        try {
          await apiService.blockThreatIP(threatId);
          showToast({
            type: 'success',
            title: 'IP bloccato',
            message: 'L\'IP è stato bloccato permanentemente'
          });
          loadThreats();
        } catch (error) {
          console.error('Error blocking IP:', error);
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile bloccare l\'IP'
          });
        }
      }
    });
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

  const getThreatScoreColor = (score: number) => {
    if (score >= 80) return 'critical';
    if (score >= 60) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  };

  const totalPages = Math.ceil(pagination.count / 20);

  return (
    <div className="firewall-logs-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            Firewall Logs
          </h1>
          <p>Pacchetti bloccati e minacce rilevate dal firewall</p>
        </div>
        <div className="header-stats">
          <div className="stat">
            <span className="stat-label">Totale Minacce</span>
            <span className="stat-value">{pagination.count.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-section">
        <div className="filters-grid">
          <div className="filter-group">
            <label>IP Sorgente</label>
            <input
              type="text"
              placeholder="Es: 192.168.1.100"
              value={filters.source_ip}
              onChange={(e) => handleFilterChange('source_ip', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Severità</label>
            <select
              value={filters.severity}
              onChange={(e) => handleFilterChange('severity', e.target.value)}
            >
              <option value="">Tutte</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Protocollo</label>
            <select
              value={filters.protocol}
              onChange={(e) => handleFilterChange('protocol', e.target.value)}
            >
              <option value="">Tutti</option>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
              <option value="icmp">ICMP</option>
            </select>
          </div>

          <div className="filter-actions">
            <button className="btn-clear" onClick={handleClearFilters}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
              Cancella
            </button>
            <button className="btn-refresh" onClick={loadThreats}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
              </svg>
              Aggiorna
            </button>
          </div>
        </div>
      </div>

      {/* Threats Table */}
      <div className="threats-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento log...</p>
          </div>
        ) : threats.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <h3>Nessuna minaccia trovata</h3>
            <p>Il firewall sta proteggendo i tuoi sistemi</p>
          </div>
        ) : (
          <div className="threats-list">
            {threats.map((threat) => (
              <div key={threat.id} className={`threat-card severity-${threat.severity}`}>
                <div className="threat-header">
                  <div className="threat-severity">
                    <span className={`severity-badge severity-${threat.severity}`}>
                      <span className="severity-icon">
                        {severityConfig[threat.severity]?.icon || '⚪'}
                      </span>
                      <span>{severityConfig[threat.severity]?.label || threat.severity}</span>
                    </span>
                    <span className="threat-score">
                      Score: <strong>{threat.threat_score}</strong>/100
                    </span>
                  </div>
                  <div className="threat-status">
                    {threat.is_blocked && (
                      <span className="status-badge blocked">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <circle cx="12" cy="12" r="10"></circle>
                          <path d="M4.93 4.93l14.14 14.14"></path>
                        </svg>
                        Bloccato
                      </span>
                    )}
                    {threat.is_resolved && (
                      <span className="status-badge resolved">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                          <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                        Risolto
                      </span>
                    )}
                  </div>
                </div>

                <div className="threat-info">
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="info-label">Target</span>
                      <span 
                        className="info-value clickable"
                        onClick={() => navigate(`/targets/${threat.target}`)}
                      >
                        {threat.target_ip}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">IP Sorgente</span>
                      <code className="info-value">{threat.source_ip}</code>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Porta Destinazione</span>
                      <code className="info-value">{threat.dest_port || '—'}</code>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Protocollo</span>
                      <span className="info-value protocol">{threat.protocol.toUpperCase()}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Pacchetti</span>
                      <span className="info-value">{threat.packet_count.toLocaleString()}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Paese</span>
                      <span className="info-value">{threat.country_code || 'Unknown'}</span>
                    </div>
                  </div>

                  {threat.attack_description && (
                    <div className="threat-description">
                      <strong>Descrizione:</strong> {threat.attack_description}
                    </div>
                  )}

                  {threat.reasons && threat.reasons.length > 0 && (
                    <div className="threat-reasons">
                      <strong>Motivi del blocco:</strong>
                      <ul>
                        {threat.reasons.map((reason, idx) => (
                          <li key={idx}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="threat-footer">
                  <div className="threat-timestamp">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    {formatTimestamp(threat.detected_at)}
                  </div>
                  <div className="threat-actions">
                    {!threat.is_resolved && (
                      <button
                        className="btn-action btn-resolve"
                        onClick={() => handleResolve(threat.id)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                          <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                        Risolvi
                      </button>
                    )}
                    {!threat.is_blocked && (
                      <button
                        className="btn-action btn-block"
                        onClick={() => handleBlock(threat.id)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <circle cx="12" cy="12" r="10"></circle>
                          <path d="M4.93 4.93l14.14 14.14"></path>
                        </svg>
                        Blocca IP
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {!loading && threats.length > 0 && (
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
            <strong>{pagination.count}</strong> minacce totali
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

export default FirewallLogs;
