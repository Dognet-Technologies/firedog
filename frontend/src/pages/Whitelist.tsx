/**
 * Whitelist Page
 * Gestione IP e subnet autorizzati permanentemente
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target } from '../types';
import './Whitelist.css';
import { useNotifications } from '../contexts/NotificationContext';

interface WhitelistEntry {
  id: number;
  ip_address: string;
  description: string;
  added_by: string;
  added_at: string;
  last_seen?: string;
  hit_count: number;
}

const Whitelist: React.FC = () => {
  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const { showToast, showConfirm } = useNotifications();
  const [searchTerm, setSearchTerm] = useState('');
  const [newEntry, setNewEntry] = useState({
    ip_address: '',
    description: '',
  });

  useEffect(() => {
    loadTargets();
  }, []);

  useEffect(() => {
    if (selectedTarget) {
      loadWhitelist();
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

  const loadWhitelist = async () => {
    if (!selectedTarget) return;

    try {
      setLoading(true);
      
      // TODO: Implementare API backend per whitelist
      // Per ora uso dati mock
      const mockEntries = generateMockWhitelist();
      setEntries(mockEntries);
      
    } catch (error) {
      console.error('Error loading whitelist:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateMockWhitelist = (): WhitelistEntry[] => {
    return [
      {
        id: 1,
        ip_address: '192.168.1.0/24',
        description: 'Rete locale ufficio',
        added_by: 'admin',
        added_at: new Date(Date.now() - 86400000 * 30).toISOString(),
        last_seen: new Date(Date.now() - 3600000).toISOString(),
        hit_count: 15234,
      },
      {
        id: 2,
        ip_address: '10.0.0.50',
        description: 'Server monitoring Nagios',
        added_by: 'admin',
        added_at: new Date(Date.now() - 86400000 * 15).toISOString(),
        last_seen: new Date(Date.now() - 300000).toISOString(),
        hit_count: 8921,
      },
      {
        id: 3,
        ip_address: '172.16.0.0/16',
        description: 'VPN aziendale',
        added_by: 'sysadmin',
        added_at: new Date(Date.now() - 86400000 * 60).toISOString(),
        last_seen: new Date(Date.now() - 7200000).toISOString(),
        hit_count: 45678,
      },
      {
        id: 4,
        ip_address: '203.0.113.10',
        description: 'API Gateway esterno',
        added_by: 'devops',
        added_at: new Date(Date.now() - 86400000 * 7).toISOString(),
        last_seen: new Date(Date.now() - 1800000).toISOString(),
        hit_count: 3421,
      },
      {
        id: 5,
        ip_address: '8.8.8.8',
        description: 'DNS Google (testing)',
        added_by: 'admin',
        added_at: new Date(Date.now() - 86400000 * 5).toISOString(),
        last_seen: new Date(Date.now() - 600000).toISOString(),
        hit_count: 1234,
      },
    ];
  };

  const handleAddEntry = async () => {
    if (!newEntry.ip_address.trim()) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Inserisci un indirizzo IP o subnet'
      });
      return;
    }

    // Validazione base IP/CIDR
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
    if (!ipRegex.test(newEntry.ip_address)) {
      showToast({
        type: 'error',
        title: 'Formato non valido',
        message: 'Usa il formato: 192.168.1.1 o 192.168.1.0/24'
      });
      return;
    }

    try {
      // TODO: Implementare API backend
      // await apiService.addWhitelistEntry(selectedTarget, newEntry);
      
      // Mock: aggiungi localmente
      const mockEntry: WhitelistEntry = {
        id: Date.now(),
        ip_address: newEntry.ip_address,
        description: newEntry.description || 'Nessuna descrizione',
        added_by: 'current_user',
        added_at: new Date().toISOString(),
        hit_count: 0,
      };
      
      setEntries([mockEntry, ...entries]);
        showToast({
          type: 'success',
          title: 'IP aggiunto',
          message: `${newEntry.ip_address} aggiunto alla whitelist`
        });
      setShowAddModal(false);
      setShowAddModal(false);
      setNewEntry({ ip_address: '', description: '' });
      
    } catch (error) {
      console.error('Error adding whitelist entry:', error);
      alert('Errore durante l\'aggiunta dell\'IP alla whitelist');
    }
  };

const handleRemoveEntry = async (id: number, ip: string) => {
    if (!window.confirm(`Rimuovere ${ip} dalla whitelist?`)) return;

    try {
      // await apiService.removeWhitelistEntry(selectedTarget, id);
      
      setEntries(entries.filter(e => e.id !== id));
      showToast({
        type: 'success',
        title: 'IP rimosso',
        message: `${ip} rimosso dalla whitelist`
      });
    } catch (error) {
      console.error('Error removing whitelist entry:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile rimuovere l\'IP dalla whitelist'
      });
    }
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

  const filteredEntries = entries.filter(entry => 
    entry.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
    entry.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="whitelist-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            Whitelist
          </h1>
          <p>Gestione IP e subnet autorizzati permanentemente</p>
        </div>
        <div className="header-actions">
          <button className="btn-primary" onClick={() => setShowAddModal(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 4v16m8-8H4"></path>
            </svg>
            Aggiungi IP
          </button>
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

        <div className="control-group search-group">
          <label>Cerca</label>
          <input
            type="text"
            placeholder="Filtra per IP o descrizione..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="stats-display">
          <span className="stat-item">
            <strong>{entries.length}</strong> entry totali
          </span>
          <span className="stat-item">
            <strong>{filteredEntries.length}</strong> visualizzate
          </span>
        </div>
      </div>

      {/* Whitelist Table */}
      <div className="whitelist-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento whitelist...</p>
          </div>
        ) : !selectedTarget ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <h3>Seleziona un Target</h3>
            <p>Scegli un target per visualizzare la sua whitelist</p>
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <h3>Nessun IP in Whitelist</h3>
            <p>Aggiungi IP o subnet autorizzati per bypassare il firewall</p>
          </div>
        ) : (
          <div className="whitelist-table-wrapper">
            <table className="whitelist-table">
              <thead>
                <tr>
                  <th>IP / Subnet</th>
                  <th>Descrizione</th>
                  <th>Aggiunto Da</th>
                  <th>Data Aggiunta</th>
                  <th>Ultimo Accesso</th>
                  <th>Hit Count</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry) => (
                  <tr key={entry.id} className="whitelist-row">
                    <td className="ip-cell">
                      <code className="ip-address">{entry.ip_address}</code>
                      {entry.ip_address.includes('/') && (
                        <span className="subnet-badge">SUBNET</span>
                      )}
                    </td>
                    <td className="description-cell">
                      {entry.description}
                    </td>
                    <td className="user-cell">
                      <div className="user-avatar">
                        {entry.added_by.charAt(0).toUpperCase()}
                      </div>
                      <span>{entry.added_by}</span>
                    </td>
                    <td className="date-cell">
                      {formatDate(entry.added_at)}
                    </td>
                    <td className="last-seen-cell">
                      {entry.last_seen ? (
                        <span className="last-seen active">
                          <span className="pulse-dot"></span>
                          {formatTimestamp(entry.last_seen)}
                        </span>
                      ) : (
                        <span className="last-seen inactive">Mai</span>
                      )}
                    </td>
                    <td className="hits-cell">
                      <span className="hit-count">
                        {entry.hit_count.toLocaleString()}
                      </span>
                    </td>
                    <td className="actions-cell">
                      <button
                        className="btn-icon btn-danger"
                        onClick={() => handleRemoveEntry(entry.id, entry.ip_address)}
                        title="Rimuovi dalla whitelist"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
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

      {/* Add Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Aggiungi IP alla Whitelist</h2>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>
                  Indirizzo IP / Subnet <span className="required">*</span>
                </label>
                <input
                  type="text"
                  placeholder="es: 192.168.1.100 o 192.168.1.0/24"
                  value={newEntry.ip_address}
                  onChange={(e) => setNewEntry({ ...newEntry, ip_address: e.target.value })}
                  autoFocus
                />
                <span className="help-text">
                  Formato supportato: IP singolo (192.168.1.1) o CIDR (192.168.1.0/24)
                </span>
              </div>

              <div className="form-group">
                <label>Descrizione</label>
                <textarea
                  placeholder="Descrizione opzionale..."
                  value={newEntry.description}
                  onChange={(e) => setNewEntry({ ...newEntry, description: e.target.value })}
                  rows={3}
                />
              </div>

              <div className="info-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <div>
                  <strong>Nota:</strong> Gli IP in whitelist bypassano completamente le regole del firewall.
                  Assicurati che siano indirizzi fidati.
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowAddModal(false)}>
                Annulla
              </button>
              <button className="btn-primary" onClick={handleAddEntry}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M12 4v16m8-8H4"></path>
                </svg>
                Aggiungi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Whitelist;
