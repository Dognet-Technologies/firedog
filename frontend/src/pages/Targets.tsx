/**
 * Targets Management Page - Table View with Gruppo
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target, TargetCreate } from '../types';
import './Targets.css';
import { useNotifications } from '../contexts/NotificationContext';

type SortField = 'ip_address' | 'hostname' | 'firedog_version' | 'last_seen' | 'status' | 'gruppo';
type SortDirection = 'asc' | 'desc';

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
    mac_address: '',
    description: '',
    group_ids: [],
  });

  // Set di target che hanno appena cambiato status verso "online" — usato per
  // animare il dot per ~10s e poi tornare statico. Niente euristiche su
  // last_seen (che si aggiorna ad ogni heartbeat e quindi è sempre "fresh"
  // per i target online).
  const [justPairedIds, setJustPairedIds] = useState<Set<number>>(new Set());
  // ref alla mappa precedente id → status, per detection delle transizioni
  // ad ogni poll. Inizialmente null → first load non triggera il pulse.
  const prevStatusRef = React.useRef<Map<number, string> | null>(null);

  useEffect(() => {
    loadTargets();
    loadGroups();
    // Auto-refresh dei target ogni 5s (status, last_seen, ecc. cambiano lato server
    // quando un agent si associa o invia heartbeat). Polling — da sostituire con
    // una subscription WebSocket dedicata quando il backend espone l'evento.
    const intervalId = setInterval(loadTargets, 5000);
    return () => clearInterval(intervalId);
  }, []);

  const loadTargets = async () => {
    try {
      const data = await apiService.getTargets();
      // Detection delle transizioni di status (X → online) per attivare il
      // pulse iniziale solo per qualche secondo. La PRIMA load non triggera
      // niente (prevStatusRef è null), così aprire la pagina non fa lampeggiare
      // tutti i target già online.
      if (prevStatusRef.current !== null) {
        const newlyOnline: number[] = [];
        for (const t of data.results) {
          const prev = prevStatusRef.current.get(t.id);
          if (prev && prev !== 'online' && t.status === 'online') {
            newlyOnline.push(t.id);
          }
        }
        if (newlyOnline.length > 0) {
          setJustPairedIds(prev => {
            const next = new Set(prev);
            newlyOnline.forEach(id => next.add(id));
            return next;
          });
          // Dopo ~10s (≈ 5 iterazioni × 2s del pulse), rimuovi la classe.
          newlyOnline.forEach(id => {
            setTimeout(() => {
              setJustPairedIds(prev => {
                const next = new Set(prev);
                next.delete(id);
                return next;
              });
            }, 10_000);
          });
        }
      }
      // Aggiorna lo snapshot per il prossimo poll
      prevStatusRef.current = new Map(data.results.map(t => [t.id, t.status]));
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
        mac_address: '',
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

  const handlePair = async (id: number, label: string, currentStatus: string) => {
    const startPair = async () => {
      try {
        const session = await apiService.startPairing(id);
        showToast({
          type: 'success',
          title: 'Pairing avviato',
          message: `Sessione #${session.id} aperta per ${label}. Avvia l'agent entro 3 minuti.`
        });
        loadTargets();
      } catch (error: unknown) {
        const msg =
          (error as { response?: { data?: { error?: string } } })?.response?.data?.error ||
          'Errore avvio pairing (controlla che IP/hostname/MAC siano impostati)';
        showToast({ type: 'error', title: 'Pairing fallito', message: msg });
      }
    };

    // Target già accoppiato in passato (online/offline/error) → chiedi
    // conferma: l'utente potrebbe aver cliccato per sbaglio sul pulsante
    // di un target che funziona già.
    const alreadyKnown = ['online', 'offline', 'error'].includes(currentStatus);
    if (alreadyKnown) {
      showConfirm({
        title: 'Riassociare il target?',
        message: `${label} è già associato (stato: ${currentStatus}). Vuoi davvero aprire una nuova sessione di pairing? L'agent corrente continua a funzionare; se la nuova sessione scade (3 min) il target torna allo stato precedente automaticamente.`,
        confirmText: 'Sì, riassocia',
        cancelText: 'Annulla',
        type: 'warning',
        onConfirm: startPair,
      });
      return;
    }
    await startPair();
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

  // Icona stato — anello colorato:
  //  verde   = paired + raggiungibile (online)
  //  rosso   = paired ma irraggiungibile (offline/error)
  //  arancio = noto ma non ancora associato (unpaired/pending/pairing)
  //  giallo  = installazione in corso
  // status-dot--just-paired è applicato solo per ~10s dopo la transizione
  // verso online (gestita da loadTargets via justPairedIds set).
  const getStatusIcon = (target: Target) => {
    const status = target.status;
    let cls = 'status-pending';
    let title = 'Pending';
    if (status === 'online') { cls = 'status-success'; title = 'Paired · online'; }
    else if (status === 'offline' || status === 'error') { cls = 'status-danger'; title = status === 'error' ? 'Error' : 'Paired · offline'; }
    else if (status === 'unpaired' || status === 'pending' || status === 'pairing') { cls = 'status-warning'; title = status === 'pairing' ? 'Pairing in progress' : 'Not paired yet'; }
    else if (status === 'installing') { cls = 'status-info'; title = 'Installing'; }
    const justPaired = justPairedIds.has(target.id) ? ' status-dot--just-paired' : '';
    return <span className={`status-dot ${cls}${justPaired}`} title={title}></span>;
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

      {/* Main content */}
      <div className="targets-content-wrapper">
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
      </div>

          {/* Targets Table */}
          <div className="targets-table-container">
        <table className="targets-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('ip_address')} className="sortable">
                IP Address {renderSortIcon('ip_address')}
              </th>
              <th title="Numero di interfacce di rete rilevate sull'host">NICs</th>
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
                <tr key={target.id} className={`target-row target-row--${target.status}`}>
                  <td className="ip-cell">
                    <code>{target.ip_address}</code>
                  </td>
                  <td className="nics-cell">
                    {(target.interfaces_count ?? 0) > 1 ? (
                      <span
                        className="version-badge"
                        title={`${target.interfaces_count} interfacce di rete rilevate`}
                      >
                        {target.interfaces_count} NIC
                      </span>
                    ) : (
                      <span className="text-muted" title="Solo l'interfaccia primaria rilevata">1</span>
                    )}
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
                    {getStatusIcon(target)}
                  </td>
                  <td className="actions-cell">
                    <div className="action-buttons">
                      <button
                        onClick={() => handlePair(target.id, target.hostname || target.ip_address, target.status)}
                        className="btn-icon"
                        title="Open pairing session (3 min) for the agent"
                        disabled={target.status === 'pairing' || target.status === 'installing'}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M10 14a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                          <path d="M14 10a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                        </svg>
                      </button>
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
                <label>MAC Address <span className="required">*</span></label>
                <input
                  type="text"
                  value={formData.mac_address || ''}
                  onChange={e => setFormData({...formData, mac_address: e.target.value})}
                  placeholder="AA:BB:CC:DD:EE:FF"
                  pattern="^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
                  required
                />
                <small style={{ color: '#888' }}>
                  Necessario per l'identity hash usato dal pairing dell'agent
                </small>
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
