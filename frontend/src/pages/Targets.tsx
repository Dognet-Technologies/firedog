/**
 * Targets Management Page - Table View
 * Gestione target con tabella ordinabile e icone stato
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target, TargetCreate } from '../types';
import './Targets.css';
import { useNotifications } from '../contexts/NotificationContext';
import SSHTerminal from '../components/SSHTerminal';

type SortField = 'ip_address' | 'hostname' | 'firedog_version' | 'last_seen' | 'status';
type SortDirection = 'asc' | 'desc';

const Targets: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const { showToast, showConfirm } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);
  const [terminalTargetId, setTerminalTargetId] = useState<number | null>(null);
  const [sortField, setSortField] = useState<SortField>('ip_address');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [formData, setFormData] = useState<TargetCreate>({
    ip_address: '',
    hostname: '',
    description: '',
  });

  useEffect(() => {
    loadTargets();
  }, []);

  const loadTargets = async () => {
    try {
      const data = await apiService.getTargets();
      setTargets(data.results);
    } catch (error) {
      console.error('Error loading targets:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare i target'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiService.createTarget(formData);
      setShowModal(false);
      setFormData({ ip_address: '', hostname: '', description: '' });
      showToast({
        type: 'success',
        title: 'Target creato',
        message: 'Target aggiunto con successo'
      });
      loadTargets();
    } catch (error) {
      console.error('Error creating target:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile creare il target'
      });
    }
  };

  const handleTestConnection = async (id: number) => {
    try {
      const result = await apiService.testConnection(id);
      
      if (result.success) {
        showToast({
          type: 'success',
          title: 'Connessione riuscita!',
          message: `SSH connection to target ${id} successful`
        });
      } else {
        showToast({
          type: 'error',
          title: 'Connessione fallita',
          message: result.error || 'Connection failed'
        });
      }
      
      loadTargets();
    } catch (error) {
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Connection test failed'
      });
    }
  };

  const handleInstall = async (id: number) => {
    const target = targets.find(t => t.id === id);
    const isReinstall = target?.firedog_version != null;
    
    showConfirm({
      title: isReinstall ? 'Conferma Reinstallazione' : 'Conferma Installazione',
      message: isReinstall 
        ? 'Vuoi reinstallare FireDog su questo target? TUTTE le regole firewall esistenti verranno rimosse. Verrà aperto un terminale SSH interattivo per completare l\'installazione.'
        : 'Vuoi installare FireDog su questo target? Verrà aperto un terminale SSH interattivo per completare l\'installazione. Assicurati di avere la password sudo del target.',
      confirmText: 'Apri Terminale',
      cancelText: 'Annulla',
      onConfirm: () => {
        setTerminalTargetId(id);
        setShowTerminal(true);
      }
    });
  };

  const handleDelete = async (id: number) => {
    showConfirm({
      title: 'Conferma Eliminazione',
      message: 'Sei sicuro di voler eliminare questo target? L\'operazione è irreversibile.',
      confirmText: 'Elimina',
      cancelText: 'Annulla',
      type: 'danger',
      onConfirm: async () => {
        try {
          await apiService.deleteTarget(id);
          showToast({
            type: 'success',
            title: 'Target eliminato',
            message: 'Target removed successfully'
          });
          loadTargets();
        } catch (error) {
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Failed to delete target'
          });
        }
      }
    });
  };

  // Funzione ordinamento
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // Toggle direction
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // Nuovo campo, default asc
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Ordina targets
  const sortedTargets = [...targets].sort((a, b) => {
    let aValue: any;
    let bValue: any;

    switch (sortField) {
      case 'ip_address':
        // Ordina IP come numeri
        aValue = a.ip_address.split('.').map(num => parseInt(num).toString().padStart(3, '0')).join('.');
        bValue = b.ip_address.split('.').map(num => parseInt(num).toString().padStart(3, '0')).join('.');
        break;
      case 'hostname':
        aValue = a.hostname || '';
        bValue = b.hostname || '';
        break;
      case 'firedog_version':
        aValue = a.firedog_version || '';
        bValue = b.firedog_version || '';
        break;
      case 'last_seen':
        aValue = a.last_seen ? new Date(a.last_seen).getTime() : 0;
        bValue = b.last_seen ? new Date(b.last_seen).getTime() : 0;
        break;
      case 'status':
        aValue = a.status;
        bValue = b.status;
        break;
      default:
        return 0;
    }

    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  // Icona stato
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return (
          <span className="status-icon status-online" title="Online">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
          </span>
        );
      case 'offline':
        return (
          <span className="status-icon status-offline" title="Offline">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
            </svg>
          </span>
        );
      case 'error':
        return (
          <span className="status-icon status-error" title="Error">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </span>
        );
      case 'installing':
        return (
          <span className="status-icon status-installing" title="Installing">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="spin">
              <path d="M21 12a9 9 0 11-6.219-8.56" />
            </svg>
          </span>
        );
      case 'pending':
        return (
          <span className="status-icon status-pending" title="Pending">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </span>
        );
      default:
        return (
          <span className="status-icon status-unknown" title="Unknown">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
          </span>
        );
    }
  };

  // Formatta Last Seen
  const formatLastSeen = (lastSeen: string | null) => {
    if (!lastSeen) return 'Never';
    
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
  };

  // Icona ordinamento
  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return (
        <svg className="sort-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M7 15l5 5 5-5M7 9l5-5 5 5" opacity="0.3" />
        </svg>
      );
    }
    
    return sortDirection === 'asc' ? (
      <svg className="sort-icon active" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M7 15l5 5 5-5" />
      </svg>
    ) : (
      <svg className="sort-icon active" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M7 9l5-5 5 5" />
      </svg>
    );
  };

  if (loading) return <div className="loading">Loading targets...</div>;

  return (
    <div className="targets-page">
      <div className="page-header">
        <div className="header-left">
          <h1>Targets Management</h1>
          <p className="subtitle">{targets.length} target{targets.length !== 1 ? 's' : ''} configurati</p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn-primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Add Target
        </button>
      </div>

      {/* Targets Table */}
      <div className="targets-table-container">
        <table className="targets-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('ip_address')} className="sortable">
                IP Address {renderSortIcon('ip_address')}
              </th>
              <th onClick={() => handleSort('hostname')} className="sortable">
                Hostname {renderSortIcon('hostname')}
              </th>
              <th onClick={() => handleSort('firedog_version')} className="sortable">
                Version {renderSortIcon('firedog_version')}
              </th>
              <th onClick={() => handleSort('last_seen')} className="sortable">
                Last Seen {renderSortIcon('last_seen')}
              </th>
              <th onClick={() => handleSort('status')} className="sortable status-col">
                Status {renderSortIcon('status')}
              </th>
              <th className="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedTargets.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-state">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <p>Nessun target configurato</p>
                  <button onClick={() => setShowModal(true)} className="btn-secondary">
                    Aggiungi il primo target
                  </button>
                </td>
              </tr>
            ) : (
              sortedTargets.map(target => (
                <tr key={target.id} className={`target-row status-${target.status}`}>
                  <td className="ip-cell">
                    <code>{target.ip_address}</code>
                  </td>
                  <td className="hostname-cell">
                    {target.hostname || <span className="text-muted">—</span>}
                  </td>
                  <td className="version-cell">
                    {target.firedog_version ? (
                      <span className="version-badge">v{target.firedog_version}</span>
                    ) : (
                      <span className="text-muted">Not installed</span>
                    )}
                  </td>
                  <td className="last-seen-cell">
                    {formatLastSeen(target.last_seen)}
                  </td>
                  <td className="status-cell">
                    {getStatusIcon(target.status)}
                  </td>
                  <td className="actions-cell">
                    <div className="action-buttons">
                      <button
                        onClick={() => handleTestConnection(target.id)}
                        className="btn-icon"
                        title="Test SSH Connection"
                        disabled={target.status === 'installing'}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                          <polyline points="22 4 12 14.01 9 11.01" />
                        </svg>
                      </button>
                      
                      {(target.status !== 'online' || !target.firedog_version) && (
                        <button
                          onClick={() => handleInstall(target.id)}
                          className="btn-icon btn-success"
                          title={target.firedog_version ? 'Reinstall FireDog' : 'Install FireDog'}
                          disabled={target.status === 'installing'}
                        >
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                          </svg>
                        </button>
                      )}
                      
                      <button
                        onClick={() => handleDelete(target.id)}
                        className="btn-icon btn-danger"
                        title="Delete Target"
                        disabled={target.status === 'installing'}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add Target Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Add New Target</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>
                  IP Address <span className="required">*</span>
                </label>
                <input
                  type="text"
                  value={formData.ip_address}
                  onChange={e => setFormData({...formData, ip_address: e.target.value})}
                  placeholder="192.168.1.100"
                  required
                />
              </div>
              <div className="form-group">
                <label>Hostname</label>
                <input
                  type="text"
                  value={formData.hostname}
                  onChange={e => setFormData({...formData, hostname: e.target.value})}
                  placeholder="server-01"
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={e => setFormData({...formData, description: e.target.value})}
                  placeholder="Optional description..."
                  rows={3}
                />
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Create Target
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SSH Terminal Modal */}
      {showTerminal && terminalTargetId && (
        <SSHTerminal
          targetId={terminalTargetId}
          onClose={() => {
            setShowTerminal(false);
            setTerminalTargetId(null);
          }}
          onInstallComplete={() => {
            loadTargets();
            setShowTerminal(false);
            setTerminalTargetId(null);
            showToast({
              type: 'success',
              title: 'Installazione completata',
              message: 'FireDog è stato installato con successo sul target'
            });
          }}
        />
      )}
    </div>
  );
};

export default Targets;
