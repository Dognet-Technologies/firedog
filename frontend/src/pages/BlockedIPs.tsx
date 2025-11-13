/**
 * Blocked IPs Page 
 * Gestione IP bloccati manualmente o automaticamente
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import './BlockedIPs.css';
import { useNotifications } from '../contexts/NotificationContext';
import { useTarget } from '../contexts/TargetContext';

interface BlockedIP {
  id: number;
  ip_address: string;
  block_reason: string;
  block_reason_display: string;
  description: string;
  blocked_by: string;
  blocked_at: string;
  threat_score: number;
  packet_count: number;
  last_attempt?: string;
  expires_at?: string;
  is_active: boolean;
  is_permanent: boolean;
}

const BlockedIPs: React.FC = () => {
  const { selectedTarget } = useTarget();
  const [blockedIPs, setBlockedIPs] = useState<BlockedIP[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const { showToast, showConfirm } = useNotifications();
  const [searchTerm, setSearchTerm] = useState('');
  const [filterReason, setFilterReason] = useState<string>('all');
  const [newBlock, setNewBlock] = useState({
    ip_address: '',
    block_reason: 'manual',
    description: '',
    threat_score: 50,
  });

  useEffect(() => {
    if (selectedTarget) {
      loadBlockedIPs();
    }
  }, [selectedTarget]);

  const loadBlockedIPs = async () => {
    if (!selectedTarget) return;

    try {
      setLoading(true);
      
      //const response = await apiService.api.get(`/blocked-ips/by_target/?target_id=${selectedTarget.id}`);
      const response = await apiService.getBlockedIPsByTarget(selectedTarget.id);
      setBlockedIPs(response.data.results || []);
      
    } catch (error) {
      console.error('Error loading blocked IPs:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare gli IP bloccati'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAddBlock = async () => {
    if (!selectedTarget) return;

    if (!newBlock.ip_address.trim()) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Inserisci un indirizzo IP'
      });
      return;
    }

    // Validazione IP
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(newBlock.ip_address)) {
      showToast({
        type: 'error',
        title: 'Formato non valido',
        message: 'Usa il formato: 192.168.1.1'
      });
      return;
    }

    try {
      await apiService.createBlockedIP({
        target: selectedTarget.id,
        ip_address: newBlock.ip_address,
        block_reason: newBlock.block_reason,
        description: newBlock.description,
        threat_score: newBlock.threat_score,
        blocked_by: 'current_user',
      });
      
      showToast({
        type: 'success',
        title: 'IP bloccato',
        message: `${newBlock.ip_address} aggiunto alla blacklist`
      });
      
      setShowAddModal(false);
      setNewBlock({
        ip_address: '',
        block_reason: 'manual',
        description: '',
        threat_score: 50,
      });
      loadBlockedIPs();
      
    } catch (error: any) {
      console.error('Error blocking IP:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: error.response?.data?.error || 'Impossibile bloccare IP'
      });
    }
  };

  const handleUnblock = async (id: number, ip: string) => {
    showConfirm({
      title: 'Conferma Sblocco',
      message: `Sbloccare ${ip}?`,
      confirmText: 'Sblocca',
      cancelText: 'Annulla',
      onConfirm: async () => {
        try {
          await apiService.unblockIP(id);
          
          showToast({
            type: 'success',
            title: 'IP sbloccato',
            message: `${ip} rimosso dalla blacklist`
          });
          
          loadBlockedIPs();
        } catch (error) {
          console.error('Error unblocking IP:', error);
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile sbloccare IP'
          });
        }
      }
    });
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = Date.now();
    const diff = now - date.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 60) return `${minutes}m fa`;
    if (hours < 24) return `${hours}h fa`;
    return `${days}g fa`;
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return new Intl.DateTimeFormat('it-IT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const getThreatColor = (score: number) => {
    if (score >= 80) return '#f44336'; // Critical
    if (score >= 60) return '#ff9800'; // High
    if (score >= 40) return '#ffc107'; // Medium
    return '#4caf50'; // Low
  };

  const filteredIPs = blockedIPs.filter(block => {
    const matchSearch = block.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
                       block.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchReason = filterReason === 'all' || block.block_reason === filterReason;
    return matchSearch && matchReason;
  });

  if (!selectedTarget) {
    return (
      <div className="blocked-ips-page">
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" />
            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
          </svg>
          <h3>Nessun Target Selezionato</h3>
          <p>Seleziona un target dal menu in alto per gestire gli IP bloccati</p>
        </div>
      </div>
    );
  }

  return (
    <div className="blocked-ips-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
            </svg>
            Blocked IPs
          </h1>
          <p>
            Target: <strong>{selectedTarget.hostname || selectedTarget.ip_address}</strong>
          </p>
        </div>
        <div className="header-actions">
          <button className="btn-primary" onClick={() => setShowAddModal(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 4v16m8-8H4"></path>
            </svg>
            Blocca IP
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="controls-section">
        <div className="control-group search-group">
          <label>Cerca</label>
          <input
            type="text"
            placeholder="Filtra per IP o descrizione..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="control-group">
          <label>Motivo Blocco</label>
          <select value={filterReason} onChange={(e) => setFilterReason(e.target.value)}>
            <option value="all">Tutti</option>
            <option value="manual">Manuale</option>
            <option value="threat_detected">Minaccia Rilevata</option>
            <option value="port_scan">Port Scan</option>
            <option value="brute_force">Brute Force</option>
            <option value="syn_flood">SYN Flood</option>
            <option value="ddos">DDoS</option>
          </select>
        </div>

        <div className="stats-display">
          <span className="stat-item">
            <strong>{blockedIPs.filter(b => b.is_active).length}</strong> bloccati
          </span>
          <span className="stat-item">
            <strong>{filteredIPs.length}</strong> visualizzati
          </span>
        </div>
      </div>

      {/* Blocked IPs Table */}
      <div className="blocked-ips-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento IP bloccati...</p>
          </div>
        ) : filteredIPs.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3>Nessun IP Bloccato</h3>
            <p>Gli IP bloccati appariranno qui</p>
          </div>
        ) : (
          <div className="blocked-ips-table-wrapper">
            <table className="blocked-ips-table">
              <thead>
                <tr>
                  <th>IP Address</th>
                  <th>Motivo</th>
                  <th>Threat Score</th>
                  <th>Packets Blocked</th>
                  <th>Bloccato Da</th>
                  <th>Data Blocco</th>
                  <th>Ultimo Tentativo</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filteredIPs.map((block) => (
                  <tr key={block.id} className="blocked-ip-row">
                    <td className="ip-cell">
                      <code className="ip-address">{block.ip_address}</code>
                      {block.is_permanent && (
                        <span className="permanent-badge">PERMANENTE</span>
                      )}
                    </td>
                    <td className="reason-cell">
                      <span className={`reason-badge reason-${block.block_reason}`}>
                        {block.block_reason_display}
                      </span>
                    </td>
                    <td className="score-cell">
                      <div className="threat-score-bar">
                        <div 
                          className="threat-score-fill"
                          style={{ 
                            width: `${block.threat_score}%`,
                            background: getThreatColor(block.threat_score)
                          }}
                        />
                        <span className="threat-score-text">{block.threat_score}/100</span>
                      </div>
                    </td>
                    <td className="packets-cell">
                      <span className="packet-count">
                        {block.packet_count.toLocaleString()}
                      </span>
                    </td>
                    <td className="user-cell">
                      <div className="user-avatar">
                        {block.blocked_by.charAt(0).toUpperCase()}
                      </div>
                      <span>{block.blocked_by}</span>
                    </td>
                    <td className="date-cell">
                      {formatDate(block.blocked_at)}
                    </td>
                    <td className="last-attempt-cell">
                      {block.last_attempt ? (
                        <span className="last-attempt">
                          {formatTimestamp(block.last_attempt)}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="actions-cell">
                      <button
                        className="btn-icon btn-success"
                        onClick={() => handleUnblock(block.id, block.ip_address)}
                        title="Sblocca IP"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <path d="M15.5 6.5A7.5 7.5 0 1023 14v-2a7.5 7.5 0 00-7.5-7.5zM1 12a11 11 0 0111-11v0" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Block Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Blocca IP</h2>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>
                  Indirizzo IP <span className="required">*</span>
                </label>
                <input
                  type="text"
                  placeholder="es: 192.168.1.100"
                  value={newBlock.ip_address}
                  onChange={(e) => setNewBlock({ ...newBlock, ip_address: e.target.value })}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label>Motivo Blocco</label>
                <select 
                  value={newBlock.block_reason}
                  onChange={(e) => setNewBlock({ ...newBlock, block_reason: e.target.value })}
                >
                  <option value="manual">Manuale</option>
                  <option value="threat_detected">Minaccia Rilevata</option>
                  <option value="port_scan">Port Scan</option>
                  <option value="brute_force">Brute Force</option>
                  <option value="syn_flood">SYN Flood</option>
                  <option value="ddos">DDoS</option>
                  <option value="malware">Malware</option>
                  <option value="other">Altro</option>
                </select>
              </div>

              <div className="form-group">
                <label>Threat Score (0-100)</label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={newBlock.threat_score}
                  onChange={(e) => setNewBlock({ ...newBlock, threat_score: parseInt(e.target.value) })}
                />
                <span className="range-value">{newBlock.threat_score}/100</span>
              </div>

              <div className="form-group">
                <label>Descrizione</label>
                <textarea
                  placeholder="Descrizione opzionale..."
                  value={newBlock.description}
                  onChange={(e) => setNewBlock({ ...newBlock, description: e.target.value })}
                  rows={3}
                />
              </div>

              <div className="warning-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <div>
                  <strong>Attenzione:</strong> L'IP verrà bloccato permanentemente.
                  Verifica che non sia un indirizzo critico per il sistema.
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowAddModal(false)}>
                Annulla
              </button>
              <button className="btn-danger" onClick={handleAddBlock}>
                Blocca IP
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BlockedIPs;
