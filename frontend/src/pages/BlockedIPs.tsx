/**
 * Blocked IPs Page
 * Gestione IP bloccati dal firewall
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target } from '../types';
import './BlockedIPs.css';
import { useNotifications } from '../contexts/NotificationContext';

interface BlockedIP {
  id: number;
  ip_address: string;
  reason: string;
  threat_score: number;
  block_type: 'manual' | 'automatic';
  blocked_by: string;
  blocked_at: string;
  packet_count: number;
  last_attempt?: string;
  country_code?: string;
  expires_at?: string | null;
}

const BlockedIPs: React.FC = () => {
  const [blockedIPs, setBlockedIPs] = useState<BlockedIP[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const { showToast, showConfirm } = useNotifications();
  const [filterType, setFilterType] = useState<string>('all');
  const [newBlock, setNewBlock] = useState({
    ip_address: '',
    reason: '',
    duration: 'permanent',
  });

  useEffect(() => {
    loadTargets();
  }, []);

  useEffect(() => {
    if (selectedTarget) {
      loadBlockedIPs();
    }
  }, [selectedTarget]);

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

  const loadBlockedIPs = async () => {
    const { showToast, showConfirm } = useNotifications();
    if (!selectedTarget) return;

    try {
      setLoading(true);
      
      // TODO: Implementare API backend per blocked IPs
      // Per ora uso dati mock
      const mockBlocked = generateMockBlockedIPs();
      setBlockedIPs(mockBlocked);
      
    } catch (error) {
      console.error('Error loading blocked IPs:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateMockBlockedIPs = (): BlockedIP[] => {
    return [
      {
        id: 1,
        ip_address: '45.142.120.10',
        reason: 'SSH Brute Force Attack',
        threat_score: 95,
        block_type: 'automatic',
        blocked_by: 'firewall-system',
        blocked_at: new Date(Date.now() - 3600000 * 2).toISOString(),
        packet_count: 15234,
        last_attempt: new Date(Date.now() - 300000).toISOString(),
        country_code: 'RU',
        expires_at: null,
      },
      {
        id: 2,
        ip_address: '103.251.167.20',
        reason: 'Port Scanning Detected',
        threat_score: 88,
        block_type: 'automatic',
        blocked_by: 'firewall-system',
        blocked_at: new Date(Date.now() - 7200000).toISOString(),
        packet_count: 8921,
        last_attempt: new Date(Date.now() - 1800000).toISOString(),
        country_code: 'CN',
        expires_at: null,
      },
      {
        id: 3,
        ip_address: '185.220.101.50',
        reason: 'Manual Block - Suspicious Activity',
        threat_score: 75,
        block_type: 'manual',
        blocked_by: 'admin',
        blocked_at: new Date(Date.now() - 86400000).toISOString(),
        packet_count: 234,
        last_attempt: new Date(Date.now() - 3600000).toISOString(),
        country_code: 'DE',
        expires_at: new Date(Date.now() + 86400000 * 7).toISOString(),
      },
      {
        id: 4,
        ip_address: '192.99.142.250',
        reason: 'DDoS Attempt',
        threat_score: 100,
        block_type: 'automatic',
        blocked_by: 'firewall-system',
        blocked_at: new Date(Date.now() - 1800000).toISOString(),
        packet_count: 45678,
        last_attempt: new Date(Date.now() - 120000).toISOString(),
        country_code: 'US',
        expires_at: null,
      },
      {
        id: 5,
        ip_address: '91.134.203.10',
        reason: 'SQL Injection Attempts',
        threat_score: 82,
        block_type: 'automatic',
        blocked_by: 'firewall-system',
        blocked_at: new Date(Date.now() - 14400000).toISOString(),
        packet_count: 3421,
        last_attempt: new Date(Date.now() - 7200000).toISOString(),
        country_code: 'FR',
        expires_at: null,
      },
    ];
  };

  const handleAddBlock = async () => {
    if (!newBlock.ip_address.trim()) {
      alert('Inserisci un indirizzo IP');
      return;
    }

    // Validazione IP
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(newBlock.ip_address)) {
      showToast({
        type: 'error',
        title: 'Formato non valido',
        message: 'Inserisci un indirizzo IP valido (es: 192.168.1.100)'
      });
      return;
    }

    try {
      // TODO: Implementare API backend
      // await apiService.blockIP(selectedTarget, newBlock);
      
      const expiresAt = newBlock.duration === 'permanent' 
        ? null 
        : new Date(Date.now() + parseInt(newBlock.duration) * 3600000).toISOString();
      
      const mockEntry: BlockedIP = {
        id: Date.now(),
        ip_address: newBlock.ip_address,
        reason: newBlock.reason || 'Manual Block',
        threat_score: 0,
        block_type: 'manual',
        blocked_by: 'current_user',
        blocked_at: new Date().toISOString(),
        packet_count: 0,
        expires_at: expiresAt,
      };
      
      setBlockedIPs([mockEntry, ...blockedIPs]);
      setShowAddModal(false);
      setNewBlock({ ip_address: '', reason: '', duration: 'permanent' });
      
    } catch (error) {
      console.error('Error blocking IP:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile bloccare l\'IP'
      });
    }

    const handleUnblock = async (id: number, ip: string) => {
      showConfirm({
        title: 'Conferma Sblocco',
        message: `Vuoi sbloccare ${ip} e permettere nuovamente il traffico?`,
        confirmText: 'Sblocca',
        cancelText: 'Annulla',
        onConfirm: async () => {
          try {
            // TODO: Implementare API backend
            // await apiService.unblockIP(selectedTarget, id);
            
            setBlockedIPs(blockedIPs.filter(b => b.id !== id));
            
            showToast({
              type: 'success',
              title: 'IP sbloccato',
              message: `${ip} è stato rimosso dalla lista bloccati`
            });
            
          } catch (error) {
            console.error('Error unblocking IP:', error);
            showToast({
              type: 'error',
              title: 'Errore',
              message: 'Impossibile sbloccare l\'IP'
            });
          }
        }
      });
    };

  const getThreatColor = (score: number) => {
    if (score >= 90) return 'critical';
    if (score >= 70) return 'high';
    if (score >= 50) return 'medium';
    return 'low';
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

  const filteredIPs = blockedIPs.filter(ip => {
    const matchesSearch = ip.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         ip.reason.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = filterType === 'all' || ip.block_type === filterType;
    return matchesSearch && matchesType;
  });

  const stats = {
    total: blockedIPs.length,
    automatic: blockedIPs.filter(ip => ip.block_type === 'automatic').length,
    manual: blockedIPs.filter(ip => ip.block_type === 'manual').length,
    permanent: blockedIPs.filter(ip => !ip.expires_at).length,
    temporary: blockedIPs.filter(ip => ip.expires_at).length,
  };

  return (
    <div className="blocked-ips-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M4.93 4.93l14.14 14.14"></path>
            </svg>
            IP Bloccati
          </h1>
          <p>Gestione IP bannati dal firewall</p>
        </div>
        <div className="header-actions">
          <button className="btn-primary" onClick={() => setShowAddModal(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M4.93 4.93l14.14 14.14"></path>
            </svg>
            Blocca IP
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon danger">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M4.93 4.93l14.14 14.14"></path>
            </svg>
          </div>
          <div className="stat-content">
            <span className="stat-label">Totale Bloccati</span>
            <span className="stat-value">{stats.total}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon warning">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>
          </div>
          <div className="stat-content">
            <span className="stat-label">Automatici</span>
            <span className="stat-value">{stats.automatic}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon info">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
            </svg>
          </div>
          <div className="stat-content">
            <span className="stat-label">Manuali</span>
            <span className="stat-value">{stats.manual}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon success">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
          <div className="stat-content">
            <span className="stat-label">Temporanei</span>
            <span className="stat-value">{stats.temporary}</span>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="controls-section">
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
          <label>Tipo</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">Tutti</option>
            <option value="automatic">Automatici</option>
            <option value="manual">Manuali</option>
          </select>
        </div>

        <div className="control-group search-group">
          <label>Cerca</label>
          <input
            type="text"
            placeholder="Filtra per IP o motivo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <button className="btn-refresh" onClick={loadBlockedIPs} disabled={loading}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"></path>
          </svg>
          Aggiorna
        </button>
      </div>

      {/* Blocked IPs List */}
      <div className="blocked-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento IP bloccati...</p>
          </div>
        ) : !selectedTarget ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M4.93 4.93l14.14 14.14"></path>
            </svg>
            <h3>Seleziona un Target</h3>
            <p>Scegli un target per visualizzare gli IP bloccati</p>
          </div>
        ) : filteredIPs.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <h3>Nessun IP Bloccato</h3>
            <p>Non ci sono IP attualmente bloccati con questi filtri</p>
          </div>
        ) : (
          <div className="blocked-list">
            {filteredIPs.map((blocked) => (
              <div key={blocked.id} className={`blocked-card threat-${getThreatColor(blocked.threat_score)}`}>
                <div className="blocked-header">
                  <div className="ip-info">
                    <code className="ip-address">{blocked.ip_address}</code>
                    {blocked.country_code && (
                      <span className="country-badge">{blocked.country_code}</span>
                    )}
                    <span className={`block-type-badge ${blocked.block_type}`}>
                      {blocked.block_type === 'automatic' ? '🤖 Auto' : '👤 Manual'}
                    </span>
                  </div>
                  <div className="threat-score-badge">
                    Score: <strong>{blocked.threat_score}</strong>/100
                  </div>
                </div>

                <div className="blocked-body">
                  <div className="info-row">
                    <span className="info-label">Motivo:</span>
                    <span className="info-value">{blocked.reason}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Bloccato da:</span>
                    <span className="info-value">{blocked.blocked_by}</span>
                  </div>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="info-label">Data Blocco</span>
                      <span className="info-value">{formatDate(blocked.blocked_at)}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Ultimo Tentativo</span>
                      <span className="info-value">
                        {blocked.last_attempt ? formatTimestamp(blocked.last_attempt) : 'N/A'}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Pacchetti</span>
                      <span className="info-value">{blocked.packet_count.toLocaleString()}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Scadenza</span>
                      <span className="info-value">
                        {blocked.expires_at ? formatDate(blocked.expires_at) : '∞ Permanente'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="blocked-footer">
                  <button
                    className="btn-unblock"
                    onClick={() => handleUnblock(blocked.id, blocked.ip_address)}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"></path>
                    </svg>
                    Sblocca IP
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Blocca Indirizzo IP</h2>
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
                <label>Motivo</label>
                <input
                  type="text"
                  placeholder="Motivo del blocco..."
                  value={newBlock.reason}
                  onChange={(e) => setNewBlock({ ...newBlock, reason: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Durata</label>
                <select
                  value={newBlock.duration}
                  onChange={(e) => setNewBlock({ ...newBlock, duration: e.target.value })}
                >
                  <option value="permanent">Permanente</option>
                  <option value="1">1 ora</option>
                  <option value="24">24 ore</option>
                  <option value="168">7 giorni</option>
                  <option value="720">30 giorni</option>
                </select>
              </div>

              <div className="warning-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                <div>
                  <strong>Attenzione:</strong> L'IP bloccato non potrà accedere a nessun servizio del target.
                  Verifica attentamente prima di procedere.
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowAddModal(false)}>
                Annulla
              </button>
              <button className="btn-danger" onClick={handleAddBlock}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path d="M4.93 4.93l14.14 14.14"></path>
                </svg>
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
