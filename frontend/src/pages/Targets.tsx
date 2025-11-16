/**
 * Targets Management Page - Table View with Gruppo
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target, TargetCreate } from '../types';
import './Targets.css';
import { useNotifications } from '../contexts/NotificationContext';
import SSHTerminal from '../components/SSHTerminal';

type SortField = 'ip_address' | 'hostname' | 'firedog_version' | 'last_seen' | 'status' | 'gruppo';
type SortDirection = 'asc' | 'desc';

// Gruppi disponibili
const GRUPPO_OPTIONS = [
  { value: '', label: 'Tutti i gruppi' },
  { value: 'web', label: 'Web Server' },
  { value: 'db', label: 'Database' },
  { value: 'dns', label: 'DNS Server' },
  { value: 'storage', label: 'Storage' },
  { value: 'mail', label: 'Mail Server' },
  { value: 'backup', label: 'Backup Server' },
  { value: 'monitoring', label: 'Monitoring' },
  { value: 'proxy', label: 'Proxy/Load Balancer' },
  { value: 'vpn', label: 'VPN Gateway' },
  { value: 'firewall', label: 'Firewall' },
  { value: 'application', label: 'Application Server' },
  { value: 'cache', label: 'Cache Server' },
  { value: 'queue', label: 'Message Queue' },
  { value: 'other', label: 'Altro' },
  { value: 'custom', label: 'Personalizzato' },
];

const Targets: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const { showToast, showConfirm } = useNotifications();
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);
  const [terminalTargetId, setTerminalTargetId] = useState<number | null>(null);
  const [sortField, setSortField] = useState<SortField>('ip_address');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [filterGruppo, setFilterGruppo] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [formData, setFormData] = useState<TargetCreate & { gruppo?: string; gruppo_custom?: string }>({
    ip_address: '',
    hostname: '',
    description: '',
    gruppo: '',
    gruppo_custom: '',
  });

  // Group installation state
  const [groupInstallQueue, setGroupInstallQueue] = useState<number[]>([]);
  const [currentGroupInstallIndex, setCurrentGroupInstallIndex] = useState(0);
  const [isGroupInstalling, setIsGroupInstalling] = useState(false);

  useEffect(() => {
    loadTargets();
  }, []);

  // Gestisce la coda di installazione di gruppo
  useEffect(() => {
    if (isGroupInstalling && groupInstallQueue.length > 0 && currentGroupInstallIndex < groupInstallQueue.length) {
      const currentTargetId = groupInstallQueue[currentGroupInstallIndex];
      setTerminalTargetId(currentTargetId);
      setShowTerminal(true);
    } else if (isGroupInstalling && currentGroupInstallIndex >= groupInstallQueue.length) {
      // Installazione gruppo completata
      setIsGroupInstalling(false);
      setGroupInstallQueue([]);
      setCurrentGroupInstallIndex(0);
      showToast({
        type: 'success',
        title: 'Installazione Gruppo Completata',
        message: `FireDog è stato installato su tutti i ${groupInstallQueue.length} target del gruppo`
      });
    }
  }, [isGroupInstalling, currentGroupInstallIndex, groupInstallQueue]);

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
    
    // Validazione gruppo custom
    if (formData.gruppo === 'custom' && !formData.gruppo_custom?.trim()) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Specifica il nome del gruppo personalizzato'
      });
      return;
    }
    
    try {
      await apiService.createTarget(formData);
      setShowModal(false);
      setFormData({ 
        ip_address: '', 
        hostname: '', 
        description: '',
        gruppo: '',
        gruppo_custom: ''
      });
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
          message: `SSH connection successful`
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
        ? 'Vuoi reinstallare FireDog su questo target? TUTTE le regole firewall esistenti verranno rimosse.'
        : 'Vuoi installare FireDog su questo target? Assicurati di avere la password sudo del target.',
      confirmText: 'Apri Terminale',
      cancelText: 'Annulla',
      onConfirm: () => {
        setTerminalTargetId(id);
        setShowTerminal(true);
      }
    });
  };

  const handleInstallGroup = () => {
    const groupTargets = filteredAndSortedTargets.filter(t => t.gruppo === filterGruppo);

    if (groupTargets.length === 0) {
      showToast({
        type: 'warning',
        title: 'Nessun Target',
        message: 'Nessun target trovato in questo gruppo'
      });
      return;
    }

    const targetIds = groupTargets.map(t => t.id);
    const gruppoLabel = GRUPPO_OPTIONS.find(g => g.value === filterGruppo)?.label || filterGruppo;

    // Alert se > 5 target
    if (groupTargets.length > 5) {
      showConfirm({
        title: 'Installazione su Gruppo',
        message: `Stai per installare FireDog su ${groupTargets.length} target del gruppo "${gruppoLabel}".\n\n⚠️ CONSIGLIO: Per accelerare l'installazione, configura prima l'accesso sudo NOPASSWD su tutti i target.\n\nSenza questa configurazione, dovrai inserire la password manualmente per ogni target (installazione sequenziale).\n\nVuoi procedere comunque?`,
        confirmText: 'Procedi con Installazione',
        cancelText: 'Annulla',
        type: 'warning',
        onConfirm: () => {
          setGroupInstallQueue(targetIds);
          setCurrentGroupInstallIndex(0);
          setIsGroupInstalling(true);
          // Il terminale verrà aperto dal useEffect
        }
      });
    } else {
      // ≤ 5 target: procedi direttamente
      showConfirm({
        title: 'Installazione su Gruppo',
        message: `Vuoi installare FireDog su ${groupTargets.length} target del gruppo "${gruppoLabel}"?\n\nL'installazione procederà in sequenza con terminale interattivo per ogni target.`,
        confirmText: 'Inizia Installazione',
        cancelText: 'Annulla',
        onConfirm: () => {
          setGroupInstallQueue(targetIds);
          setCurrentGroupInstallIndex(0);
          setIsGroupInstalling(true);
        }
      });
    }
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
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Filtra e ordina targets
  const filteredAndSortedTargets = targets
    .filter(target => {
      const matchesSearch = 
        target.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (target.hostname || '').toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesGruppo = !filterGruppo || target.gruppo === filterGruppo;
      
      return matchesSearch && matchesGruppo;
    })
    .sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'ip_address':
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
        case 'gruppo':
          aValue = a.gruppo_display || '';
          bValue = b.gruppo_display || '';
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
        return <span className="status-dot status-online" title="Online"></span>;
      case 'offline':
        return <span className="status-dot status-offline" title="Offline"></span>;
      case 'error':
        return <span className="status-dot status-error" title="Error"></span>;
      case 'installing':
        return <span className="status-dot status-installing" title="Installing"></span>;
      default:
        return <span className="status-dot status-pending" title="Pending"></span>;
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

  // Badge gruppo
  const getGruppoBadge = (target: Target) => {
    const hasStaticGruppo = target.gruppo && target.gruppo.trim() !== '';
    const hasTargetGroups = target.target_groups && target.target_groups.length > 0;

    if (!hasStaticGruppo && !hasTargetGroups) {
      return <span className="gruppo-badge gruppo-none">—</span>;
    }

    return (
      <div className="gruppo-badges-container">
        {/* Campo gruppo statico */}
        {hasStaticGruppo && (
          <span className={`gruppo-badge gruppo-${target.gruppo}`}>
            {target.gruppo_display || target.gruppo}
          </span>
        )}

        {/* TargetGroups dalla tab Groups */}
        {hasTargetGroups && target.target_groups!.map((group) => (
          <span
            key={group.id}
            className="gruppo-badge gruppo-targetgroup"
            style={{ backgroundColor: group.color + '20', borderColor: group.color, color: group.color }}
            title={`TargetGroup: ${group.name}`}
          >
            {group.name}
          </span>
        ))}
      </div>
    );
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

      {/* Filtri */}
      <div className="filters-section">
        <div className="filter-group">
          <label>Cerca</label>
          <input
            type="text"
            placeholder="IP o hostname..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="filter-input"
          />
        </div>

        <div className="filter-group">
          <label>Gruppo</label>
          <select
            value={filterGruppo}
            onChange={(e) => setFilterGruppo(e.target.value)}
            className="filter-select"
          >
            {GRUPPO_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-stats">
          <span>Visualizzati: <strong>{filteredAndSortedTargets.length}</strong></span>
        </div>

        {/* Install on Group Button */}
        {filterGruppo && filteredAndSortedTargets.length > 0 && (
          <button
            onClick={handleInstallGroup}
            className="btn-primary btn-install-group"
            disabled={isGroupInstalling}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {isGroupInstalling
              ? `Installing ${currentGroupInstallIndex + 1}/${groupInstallQueue.length}...`
              : `Install on Group (${filteredAndSortedTargets.length})`}
          </button>
        )}
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
              <th onClick={() => handleSort('gruppo')} className="sortable">
                Gruppo {renderSortIcon('gruppo')}
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
            {filteredAndSortedTargets.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <p>Nessun target trovato</p>
                </td>
              </tr>
            ) : (
              filteredAndSortedTargets.map(target => (
                <tr key={target.id} className={`target-row status-${target.status}`}>
                  <td className="ip-cell">
                    <code>{target.ip_address}</code>
                  </td>
                  <td className="hostname-cell">
                    {target.hostname || <span className="text-muted">—</span>}
                  </td>
                  <td className="gruppo-cell">
                    {getGruppoBadge(target)}
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
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>IP Address <span className="required">*</span></label>
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
                <label>Gruppo</label>
                <select
                  value={formData.gruppo || ''}
                  onChange={e => setFormData({...formData, gruppo: e.target.value})}
                >
                  {GRUPPO_OPTIONS.slice(1).map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              {formData.gruppo === 'custom' && (
                <div className="form-group">
                  <label>Nome Gruppo Personalizzato <span className="required">*</span></label>
                  <input
                    type="text"
                    value={formData.gruppo_custom || ''}
                    onChange={e => setFormData({...formData, gruppo_custom: e.target.value})}
                    placeholder="es: IoT Devices"
                    required
                  />
                </div>
              )}
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
            if (isGroupInstalling) {
              // Annulla installazione gruppo
              setIsGroupInstalling(false);
              setGroupInstallQueue([]);
              setCurrentGroupInstallIndex(0);
            }
          }}
          onInstallComplete={() => {
            loadTargets();

            if (isGroupInstalling) {
              // Installazione di gruppo: passa al prossimo target
              const nextIndex = currentGroupInstallIndex + 1;
              const currentTarget = targets.find(t => t.id === terminalTargetId);

              showToast({
                type: 'success',
                title: `Target ${nextIndex}/${groupInstallQueue.length} Completato`,
                message: `${currentTarget?.hostname || currentTarget?.ip_address} installato con successo`
              });

              setShowTerminal(false);
              setTerminalTargetId(null);

              // Passa al prossimo dopo un breve delay
              setTimeout(() => {
                setCurrentGroupInstallIndex(nextIndex);
              }, 500);
            } else {
              // Installazione singola: chiudi normalmente
              setShowTerminal(false);
              setTerminalTargetId(null);
              showToast({
                type: 'success',
                title: 'Installazione completata',
                message: 'FireDog è stato installato con successo sul target'
              });
            }
          }}
        />
      )}
    </div>
  );
};

export default Targets;
