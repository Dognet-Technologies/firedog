import React, { useState, useEffect } from 'react';
import threatsService, { ThreatLog, ThreatStats, ThreatsFilter } from '../services/threats.service';
import { useTarget } from '../contexts/TargetContext';
import './Threats.css';

const Threats: React.FC = () => {
  const { selectedTarget } = useTarget();

  const [threats, setThreats] = useState<ThreatLog[]>([]);
  const [stats, setStats] = useState<ThreatStats | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Filtri — inizializza con il target globale se presente
  const [filters, setFilters] = useState<ThreatsFilter>({
    severity: undefined,
    is_resolved: false,
    limit: 50,
    target: selectedTarget?.id,
  });

  // Dettaglio minaccia selezionata
  const [selectedThreat, setSelectedThreat] = useState<ThreatLog | null>(null);
  const [showDetailModal, setShowDetailModal] = useState<boolean>(false);

  // Aggiorna il filtro target quando cambia il target globale
  useEffect(() => {
    setFilters((prev) => ({ ...prev, target: selectedTarget?.id }));
  }, [selectedTarget?.id]);

  useEffect(() => {
    loadThreats();
    loadStats();
  }, [filters.target]);

  const loadThreats = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await threatsService.getThreats(filters);
      setThreats(data.results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await threatsService.getStats();
      setStats(data);
    } catch (err: any) {
      console.error('Error loading stats:', err);
    }
  };

  const handleFilterChange = (key: keyof ThreatsFilter, value: any) => {
    setFilters({ ...filters, [key]: value });
  };

  const applyFilters = () => {
    loadThreats();
  };

  const handleResolve = async (threatId: number) => {
    if (!window.confirm('Segnare questa minaccia come risolta?')) {
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await threatsService.resolveThreat(threatId);
      setSuccess('Minaccia risolta con successo');
      await loadThreats();
      await loadStats();
      setShowDetailModal(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openDetail = (threat: ThreatLog) => {
    setSelectedThreat(threat);
    setShowDetailModal(true);
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case 'critical':
        return '#ff4d4d';
      case 'high':
        return '#ff9500';
      case 'medium':
        return '#ffcc00';
      case 'low':
        return '#7dffaa';
      default:
        return '#8e91a1';
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="threats-page">
      {/* Header con Statistiche */}
      <div className="page-header">
        <div className="header-left">
          <h1>Threats Analysis</h1>
          <p className="subtitle">Analisi minacce e traffico bloccato</p>
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
            <div className="stat-value">{stats.total_threats}</div>
            <div className="stat-label">Minacce Totali</div>
          </div>
          <div className="stat-card critical">
            <div className="stat-value">{stats.critical_threats}</div>
            <div className="stat-label">Critical</div>
          </div>
          <div className="stat-card high">
            <div className="stat-value">{stats.high_threats}</div>
            <div className="stat-label">High</div>
          </div>
          <div className="stat-card medium">
            <div className="stat-value">{stats.medium_threats}</div>
            <div className="stat-label">Medium</div>
          </div>
          <div className="stat-card low">
            <div className="stat-value">{stats.low_threats}</div>
            <div className="stat-label">Low</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.blocked_ips}</div>
            <div className="stat-label">IP Bloccati</div>
          </div>
        </div>
      )}

      {/* Filtri */}
      <div className="filters-section">
        <h3>Filtri</h3>
        <div className="filters-grid">
          <div className="filter-group">
            <label>Severity</label>
            <select
              value={filters.severity || ''}
              onChange={(e) => handleFilterChange('severity', e.target.value || undefined)}
              className="filter-select"
            >
              <option value="">Tutte</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Stato</label>
            <select
              value={filters.is_resolved === undefined ? '' : filters.is_resolved ? 'resolved' : 'unresolved'}
              onChange={(e) => {
                const value = e.target.value;
                handleFilterChange('is_resolved', value === '' ? undefined : value === 'resolved');
              }}
              className="filter-select"
            >
              <option value="">Tutte</option>
              <option value="unresolved">Non Risolte</option>
              <option value="resolved">Risolte</option>
            </select>
          </div>

          <div className="filter-group">
            <label>IP Sorgente</label>
            <input
              type="text"
              placeholder="es. 192.168.1.100"
              value={filters.source_ip || ''}
              onChange={(e) => handleFilterChange('source_ip', e.target.value || undefined)}
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label>Score Minimo</label>
            <input
              type="number"
              min="0"
              max="100"
              placeholder="0-100"
              value={filters.min_score || ''}
              onChange={(e) => handleFilterChange('min_score', e.target.value ? parseInt(e.target.value) : undefined)}
              className="filter-input"
            />
          </div>
        </div>
        <button className="btn-apply-filters" onClick={applyFilters} disabled={loading}>
          {loading ? 'Caricamento...' : 'Applica Filtri'}
        </button>
      </div>

      {/* Top Attackers */}
      {stats && stats.top_attackers.length > 0 && (
        <div className="top-attackers-section">
          <h3>Top Attackers</h3>
          <div className="attackers-grid">
            {stats.top_attackers.slice(0, 5).map((attacker, index) => (
              <div key={index} className="attacker-card">
                <div className="attacker-rank">#{index + 1}</div>
                <div className="attacker-ip">{attacker.source_ip}</div>
                <div className="attacker-count">{attacker.count} attacchi</div>
                <div className="attacker-score">Score: {attacker.max_score}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Threats Table */}
      <div className="threats-section">
        <h3>Minacce Rilevate</h3>
        {loading && threats.length === 0 ? (
          <div className="loading-spinner">Caricamento minacce...</div>
        ) : threats.length === 0 ? (
          <div className="no-data">Nessuna minaccia trovata</div>
        ) : (
          <div className="table-container">
            <table className="threats-table">
              <thead>
                <tr>
                  <th>IP Sorgente</th>
                  <th>Porta Dest</th>
                  <th>Protocollo</th>
                  <th>Score</th>
                  <th>Severity</th>
                  <th>Pacchetti</th>
                  <th>Paese</th>
                  <th>Rilevata</th>
                  <th>Stato</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {threats.map((threat) => (
                  <tr key={threat.id} className={threat.is_resolved ? 'resolved-row' : ''}>
                    <td className="ip-cell">{threat.source_ip}</td>
                    <td>{threat.dest_port || '-'}</td>
                    <td>
                      <span className="protocol-badge">{threat.protocol.toUpperCase()}</span>
                    </td>
                    <td>
                      <span className="score-badge" style={{ background: `rgba(${255 - threat.threat_score * 2.55}, ${threat.threat_score * 2.55}, 0, 0.2)` }}>
                        {threat.threat_score}
                      </span>
                    </td>
                    <td>
                      <span
                        className="severity-badge"
                        style={{ 
                          background: `${getSeverityColor(threat.severity)}33`,
                          color: getSeverityColor(threat.severity),
                          border: `1px solid ${getSeverityColor(threat.severity)}66`
                        }}
                      >
                        {threat.severity.toUpperCase()}
                      </span>
                    </td>
                    <td>{threat.packet_count}</td>
                    <td>
                      <span className="country-badge">{threat.country_code || '??'}</span>
                    </td>
                    <td className="date-cell">{formatDate(threat.detected_at)}</td>
                    <td>
                      {threat.is_resolved ? (
                        <span className="status-resolved">✓ Risolta</span>
                      ) : (
                        <span className="status-active">● Attiva</span>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn-detail"
                        onClick={() => openDetail(threat)}
                      >
                        Dettagli
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
      {showDetailModal && selectedThreat && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Dettagli Minaccia</h3>
              <button className="modal-close" onClick={() => setShowDetailModal(false)}>×</button>
            </div>
            
            <div className="detail-body">
              <div className="detail-row">
                <span className="detail-label">IP Sorgente:</span>
                <span className="detail-value ip-value">{selectedThreat.source_ip}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Porta Destinazione:</span>
                <span className="detail-value">{selectedThreat.dest_port || 'N/A'}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Protocollo:</span>
                <span className="detail-value">{selectedThreat.protocol.toUpperCase()}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Threat Score:</span>
                <span className="detail-value score-value">{selectedThreat.threat_score}/100</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Severity:</span>
                <span
                  className="severity-badge"
                  style={{ 
                    background: `${getSeverityColor(selectedThreat.severity)}33`,
                    color: getSeverityColor(selectedThreat.severity),
                    border: `1px solid ${getSeverityColor(selectedThreat.severity)}66`
                  }}
                >
                  {selectedThreat.severity.toUpperCase()}
                </span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Pacchetti:</span>
                <span className="detail-value">{selectedThreat.packet_count}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Paese:</span>
                <span className="detail-value">{selectedThreat.country_code || 'Sconosciuto'}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Descrizione:</span>
                <span className="detail-value">{selectedThreat.description}</span>
              </div>

              {selectedThreat.reasons && selectedThreat.reasons.length > 0 && (
                <div className="detail-row full-width">
                  <span className="detail-label">Motivi:</span>
                  <ul className="reasons-list">
                    {selectedThreat.reasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="detail-row">
                <span className="detail-label">Rilevata:</span>
                <span className="detail-value">{formatDate(selectedThreat.detected_at)}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Stato:</span>
                {selectedThreat.is_resolved ? (
                  <span className="status-resolved">✓ Risolta il {selectedThreat.resolved_at ? formatDate(selectedThreat.resolved_at) : 'N/A'}</span>
                ) : (
                  <span className="status-active">● Attiva</span>
                )}
              </div>
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowDetailModal(false)}
              >
                Chiudi
              </button>
              {!selectedThreat.is_resolved && (
                <button
                  className="btn-primary"
                  onClick={() => handleResolve(selectedThreat.id)}
                  disabled={loading}
                >
                  {loading ? 'Elaborazione...' : 'Segna come Risolta'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Threats;
