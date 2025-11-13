/**
 * Whitelist Page
 * Gestione IP e subnet autorizzati permanentemente
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import './Whitelist.css';
import { useNotifications } from '../contexts/NotificationContext';
import { useTarget } from '../contexts/TargetContext';

interface WhitelistEntry {
  id: number;
  ip_address: string;
  description: string;
  added_by: string;
  added_at: string;
  last_seen?: string;
  hit_count: number;
  is_active: boolean;
}

const Whitelist: React.FC = () => {
  const { selectedTarget } = useTarget();
  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const { showToast, showConfirm } = useNotifications();
  const [searchTerm, setSearchTerm] = useState('');
  const [newEntry, setNewEntry] = useState({
    ip_address: '',
    description: '',
  });

  useEffect(() => {
    if (selectedTarget) {
      loadWhitelist();
    }
  }, [selectedTarget]);

  const loadWhitelist = async () => {
    if (!selectedTarget) return;

    try {
      setLoading(true);
      
      // API call per whitelist
      const response = await apiService.getWhitelistByTarget(selectedTarget.id);
      setEntries(response.data.results || []);
      
    } catch (error) {
      console.error('Error loading whitelist:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare la whitelist'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAddEntry = async () => {
    if (!selectedTarget) return;

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
      await apiService.createWhitelistEntry({
        target: selectedTarget.id,
        ip_address: newEntry.ip_address,
        description: newEntry.description,
        added_by: 'current_user',
      });
      
      showToast({
        type: 'success',
        title: 'IP aggiunto',
        message: `${newEntry.ip_address} aggiunto alla whitelist`
      });
      
      setShowAddModal(false);
      setNewEntry({ ip_address: '', description: '' });
      loadWhitelist();
      
    } catch (error: any) {
      console.error('Error adding whitelist entry:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: error.response?.data?.error || 'Impossibile aggiungere IP alla whitelist'
      });
    }
  };

  const handleRemoveEntry = async (id: number, ip: string) => {
    showConfirm({
      title: 'Conferma Rimozione',
      message: `Rimuovere ${ip} dalla whitelist?`,
      confirmText: 'Rimuovi',
      cancelText: 'Annulla',
      type: 'danger',
      onConfirm: async () => {
        try {
          await apiService.deleteWhitelistEntry(id);
          
          showToast({
            type: 'success',
            title: 'IP rimosso',
            message: `${ip} rimosso dalla whitelist`
          });
          
          loadWhitelist();
        } catch (error) {
          console.error('Error removing whitelist entry:', error);
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile rimuovere l\'IP dalla whitelist'
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

  const filteredEntries = entries.filter(entry => 
    entry.is_active && (
      entry.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.description.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  if (!selectedTarget) {
    return (
      <div className="whitelist-page">
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" />
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3>Nessun Target Selezionato</h3>
          <p>Seleziona un target dal menu in alto per gestire la whitelist</p>
        </div>
      </div>
    );
  }

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
          <p>
            Target: <strong>{selectedTarget.hostname || selectedTarget.ip_address}</strong>
          </p>
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
            <strong>{entries.filter(e => e.is_active).length}</strong> entry attive
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
        ) : filteredEntries.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            <h3>Nessun IP in Whitelist</h3>
            <p>Aggiungi IP o subnet autorizzati per bypassare il firewall</p>
            <button className="btn-secondary" onClick={() => setShowAddModal(true)}>
              Aggiungi primo IP
            </button>
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
                      {entry.description || '—'}
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
