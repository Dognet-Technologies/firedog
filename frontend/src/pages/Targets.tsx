/**
 * Targets Management Page - Table View with Gruppo
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target, TargetCreate } from '../types';
import './Targets.css';
import { useNotifications } from '../contexts/NotificationContext';
import CollapsibleTerminalPanel from '../components/CollapsibleTerminalPanel';
import TabbedTerminalManager, { TerminalOperation } from '../components/TabbedTerminalManager';

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
  const [sortField, setSortField] = useState<SortField>('ip_address');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [filterGruppo, setFilterGruppo] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [availableGroups, setAvailableGroups] = useState<any[]>([]);
  const [formData, setFormData] = useState<TargetCreate & { group_ids?: number[] }>({
    ip_address: '',
    hostname: '',
    description: '',
    group_ids: [],
  });

  // Terminal operations state (max 5 parallel)
  const [terminalOperations, setTerminalOperations] = useState<TerminalOperation[]>([]);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [queuedTargets, setQueuedTargets] = useState<Target[]>([]);

  useEffect(() => {
    loadTargets();
    loadGroups();
  }, []);

  // Auto-fill slots when operations complete and queue has items
  useEffect(() => {
    if (queuedTargets.length > 0 && terminalOperations.length < 5) {
      const slotsAvailable = 5 - terminalOperations.length;
      const targetsToAdd = queuedTargets.slice(0, slotsAvailable);
      const remainingQueue = queuedTargets.slice(slotsAvailable);

      const newOperations: TerminalOperation[] = targetsToAdd.map(target => ({
        id: `op-${Date.now()}-${Math.random()}`,
        target,
        type: target.firedog_version ? 'reinstall' : 'install',
        status: 'running',
        requiresFocus: false
      }));

      setTerminalOperations(prev => [...prev, ...newOperations]);
      setQueuedTargets(remainingQueue);
    }
  }, [queuedTargets, terminalOperations]);

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

  const loadGroups = async () => {
    try {
      const groups = await apiService.getGroups();
      setAvailableGroups(groups);
    } catch (error) {
      console.error('Error loading groups:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare i gruppi'
      });
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await apiService.createTarget(formData);
      setShowModal(false);
      setFormData({
        ip_address: '',
        hostname: '',
        description: '',
        group_ids: []
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
    if (!target) return;

    const isReinstall = target.firedog_version != null;

    // Check if we can add more operations
    if (terminalOperations.length >= 5) {
      showToast({
        type: 'warning',
        title: 'Troppi Operazioni',
        message: 'Max 5 installazioni parallele. Completa o chiudi alcune operazioni prima di procedere.'
      });
      return;
    }

    showConfirm({
      title: isReinstall ? 'Conferma Reinstallazione' : 'Conferma Installazione',
      message: isReinstall
        ? 'Vuoi reinstallare FireDog su questo target? TUTTE le regole firewall esistenti verranno rimosse.'
        : 'Vuoi installare FireDog su questo target? Assicurati di avere la password sudo del target.',
      confirmText: 'Avvia Installazione',
      cancelText: 'Annulla',
      onConfirm: () => {
        const newOperation: TerminalOperation = {
          id: `op-${Date.now()}-${Math.random()}`,
          target,
          type: isReinstall ? 'reinstall' : 'install',
          status: 'running',
          requiresFocus: false
        };

        setTerminalOperations(prev => [...prev, newOperation]);
        setIsPanelOpen(true);

        showToast({
          type: 'info',
          title: 'Installazione Avviata',
          message: `Installazione su ${target.hostname || target.ip_address} avviata`
        });
      }
    });
  };

  const handleInstallGroup = () => {
    const groupTargets = filteredAndSortedTargets.filter(t =>
      t.target_groups?.some(g => g.name === filterGruppo)
    );

    if (groupTargets.length === 0) {
      showToast({
        type: 'warning',
        title: 'Nessun Target',
        message: 'Nessun target trovato in questo gruppo'
      });
      return;
    }

    const gruppoLabel = filterGruppo;

    // Alert se > 5 target
    if (groupTargets.length > 5) {
      showConfirm({
        title: 'Installazione su Gruppo',
        message: `Stai per installare FireDog su ${groupTargets.length} target del gruppo "${gruppoLabel}".\n\n✓ Verranno eseguite max 5 installazioni in parallelo\n⚠️ CONSIGLIO: Configura sudo NOPASSWD per accelerare il processo\n\nVuoi procedere?`,
        confirmText: 'Procedi con Installazione',
        cancelText: 'Annulla',
        type: 'warning',
        onConfirm: () => {
          // Primi 5 vanno subito nelle operazioni attive
          const batch = groupTargets.slice(0, 5);
          const queued = groupTargets.slice(5);

          const newOperations: TerminalOperation[] = batch.map(target => ({
            id: `op-${Date.now()}-${Math.random()}`,
            target,
            type: target.firedog_version ? 'reinstall' : 'install',
            status: 'running',
            requiresFocus: false
          }));

          setTerminalOperations(newOperations);
          setQueuedTargets(queued);
          setIsPanelOpen(true);

          showToast({
            type: 'info',
            title: 'Installazione Gruppo Avviata',
            message: `Installazione su ${batch.length} target in parallelo. ${queued.length} in coda.`
          });
        }
      });
    } else {
      // ≤ 5 target: tutti in parallelo
      showConfirm({
        title: 'Installazione su Gruppo',
        message: `Vuoi installare FireDog su ${groupTargets.length} target del gruppo "${gruppoLabel}"?\n\nTutti i target verranno processati in parallelo.`,
        confirmText: 'Inizia Installazione',
        cancelText: 'Annulla',
        onConfirm: () => {
          const newOperations: TerminalOperation[] = groupTargets.map(target => ({
            id: `op-${Date.now()}-${Math.random()}`,
            target,
            type: target.firedog_version ? 'reinstall' : 'install',
            status: 'running',
            requiresFocus: false
          }));

          setTerminalOperations(newOperations);
          setIsPanelOpen(true);

          showToast({
            type: 'info',
            title: 'Installazione Gruppo Avviata',
            message: `Installazione su ${groupTargets.length} target in parallelo`
          });
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

  // Terminal operation handlers
  const handleOperationComplete = (operationId: string) => {
    const operation = terminalOperations.find(op => op.id === operationId);

    if (operation) {
      showToast({
        type: 'success',
        title: 'Installazione Completata',
        message: `${operation.target.hostname || operation.target.ip_address} installato con successo`
      });
    }

    // Rimuovi l'operazione completata
    setTerminalOperations(prev => prev.filter(op => op.id !== operationId));
    loadTargets();

    // Se non ci sono più operazioni e la coda è vuota, chiudi il panel
    if (terminalOperations.length === 1 && queuedTargets.length === 0) {
      setTimeout(() => setIsPanelOpen(false), 1000);
    }
  };

  const handleOperationError = (operationId: string) => {
    const operation = terminalOperations.find(op => op.id === operationId);

    if (operation) {
      showToast({
        type: 'error',
        title: 'Errore Installazione',
        message: `Errore su ${operation.target.hostname || operation.target.ip_address}`
      });
    }
  };

  const handleCloseOperation = (operationId: string) => {
    setTerminalOperations(prev => prev.filter(op => op.id !== operationId));

    // Se non ci sono più operazioni, chiudi il panel
    if (terminalOperations.length === 1 && queuedTargets.length === 0) {
      setIsPanelOpen(false);
      setQueuedTargets([]); // Clear queue
    }
  };

  const handleUpdateOperation = (operationId: string, updates: Partial<TerminalOperation>) => {
    setTerminalOperations(prev =>
      prev.map(op => (op.id === operationId ? { ...op, ...updates } : op))
    );
  };

  const handleClosePanel = () => {
    if (terminalOperations.length > 0) {
      showConfirm({
        title: 'Chiudi Panel',
        message: 'Ci sono operazioni in corso. Sei sicuro di voler chiudere? Le operazioni verranno interrotte.',
        confirmText: 'Chiudi',
        cancelText: 'Annulla',
        type: 'warning',
        onConfirm: () => {
          setTerminalOperations([]);
          setQueuedTargets([]);
          setIsPanelOpen(false);
        }
      });
    } else {
      setIsPanelOpen(false);
      setQueuedTargets([]);
    }
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

      const matchesGruppo = !filterGruppo ||
        target.target_groups?.some(g => g.name === filterGruppo) ||
        false;

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
          aValue = a.target_groups?.[0]?.name || '';
          bValue = b.target_groups?.[0]?.name || '';
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
    const hasTargetGroups = target.target_groups && target.target_groups.length > 0;

    if (!hasTargetGroups) {
      return <span className="gruppo-badge gruppo-none">—</span>;
    }

    return (
      <div className="gruppo-badges-container">
        {/* TargetGroups */}
        {target.target_groups!.map((group) => (
          <span
            key={group.id}
            className="gruppo-badge gruppo-targetgroup"
            style={{ backgroundColor: group.color + '20', borderColor: group.color, color: group.color }}
            title={`Gruppo: ${group.name}`}
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

      {/* Main content with split layout */}
      <div className={`targets-content-wrapper ${isPanelOpen ? 'panel-open' : ''}`}>
        <div className="targets-main-content">
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
            <option value="">Tutti i gruppi</option>
            {availableGroups.map(group => (
              <option key={group.id} value={group.name}>{group.name}</option>
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
            disabled={terminalOperations.length >= 5}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {terminalOperations.length > 0
              ? `Installing (${terminalOperations.length} active)...`
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
        </div>

        {/* Collapsible Terminal Panel - Right Sidebar */}
        <CollapsibleTerminalPanel
          isOpen={isPanelOpen}
          onClose={handleClosePanel}
          title={`Installation Progress ${queuedTargets.length > 0 ? `(${queuedTargets.length} in queue)` : ''}`}
        >
          <TabbedTerminalManager
            operations={terminalOperations}
            onOperationComplete={handleOperationComplete}
            onOperationError={handleOperationError}
            onCloseOperation={handleCloseOperation}
            onUpdateOperation={handleUpdateOperation}
          />
        </CollapsibleTerminalPanel>
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
                <label>Gruppi (seleziona uno o più)</label>
                <select
                  multiple
                  value={formData.group_ids?.map(String) || []}
                  onChange={e => {
                    const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                    setFormData({...formData, group_ids: selected});
                  }}
                  style={{ minHeight: '120px' }}
                >
                  {availableGroups.map(group => (
                    <option key={group.id} value={group.id}>{group.name}</option>
                  ))}
                </select>
                <small style={{ color: '#888' }}>Tieni premuto Ctrl (Cmd su Mac) per selezionare più gruppi</small>
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
    </div>
  );
};

export default Targets;
