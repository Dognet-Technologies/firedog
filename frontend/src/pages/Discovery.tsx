/**
 * Discovery Page - Network Discovery e Import Target + Groups
 * 
 * 4 Modalità:
 * 1. ARP-Scan Network Discovery
 * 2. Bulk Import da File
 * 3. Aggiunta Manuale
 * 4. Groups Management (NEW)
 */
import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import apiService from '../services/api';
import type { DiscoveredHost, Target } from '../types';
import { useNotifications } from '../contexts/NotificationContext';
import './Discovery.css';

interface ScanStatus {
  status: 'idle' | 'scanning' | 'completed' | 'error';
  taskId?: string;
  message?: string;
}

interface BulkImportResult {
  imported: number;
  skipped: number;
  errors: Array<{ line: number; error: string; content: string }>;
}

interface TargetGroup {
  id: number;
  name: string;
  description: string;
  color: string;
  icon: string;
  target_count: number;
  online_count: number;
  targets?: Target[];
  created_at: string;
  updated_at: string;
}

const Discovery: React.FC = () => {
  // ?tab=arp-scan|file|manual|groups & ?group=<id> consente di linkare
  // direttamente al tab Groups con un gruppo pre-selezionato (es. dalla
  // pagina /groups cliccando "+ Add Target").
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const tabParam = queryParams.get('tab') as 'arp-scan' | 'file' | 'manual' | 'groups' | null;
  const groupParam = queryParams.get('group');

  // State
  const [activeTab, setActiveTab] = useState<'arp-scan' | 'file' | 'manual' | 'groups'>(
    (tabParam && ['arp-scan', 'file', 'manual', 'groups'].includes(tabParam)) ? tabParam : 'arp-scan'
  );
  const [discoveredHosts, setDiscoveredHosts] = useState<DiscoveredHost[]>([]);
  const [selectedHosts, setSelectedHosts] = useState<Set<number>>(new Set());
  const { showToast, showConfirm } = useNotifications();
  const [scanStatus, setScanStatus] = useState<ScanStatus>({ status: 'idle' });
  const [loading, setLoading] = useState(false);
  
  // File import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<BulkImportResult | null>(null);
  
  // Manual add state
  const [manualForm, setManualForm] = useState({
    ip_address: '',
    hostname: '',
    mac_address: '',
    description: '',
    group_ids: [] as number[]
  });
  const [availableGroups, setAvailableGroups] = useState<any[]>([]);

  // Groups state (NEW)
  const [groups, setGroups] = useState<TargetGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<TargetGroup | null>(null);
  const [availableTargets, setAvailableTargets] = useState<Target[]>([]);
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [newGroupForm, setNewGroupForm] = useState({
    name: '',
    description: '',
    color: '#3b82f6',
    icon: 'server'
  });

  // Load data on mount
  useEffect(() => {
    loadDiscoveredHosts();
    loadAvailableGroups();
  }, []);

  // Load groups when tab changes
  useEffect(() => {
    if (activeTab === 'groups') {
      loadGroups();
    }
  }, [activeTab]);

  // Poll scan status
  useEffect(() => {
    if (scanStatus.status === 'scanning' && scanStatus.taskId) {
      const interval = setInterval(async () => {
        try {
          const response = await apiService.getDiscoveryScanStatus(scanStatus.taskId!);

          if (response.status === 'SUCCESS') {
            // Il task Celery è terminato senza eccezioni, ma la business-logic
            // interna può comunque avere fallito (es. arp-scan binary mancante,
            // o tutte le reti scansionate in errore). Verifichiamo result.success
            // prima di dichiarare lo scan riuscito.
            const result = (response as { result?: { success?: boolean; error?: string; hosts_found?: number; network_errors?: Record<string, string> } }).result;
            if (result && result.success === false) {
              const detail = result.network_errors
                ? Object.entries(result.network_errors).map(([net, err]) => `${net}: ${err}`).join(' · ')
                : result.error || 'Scan fallito senza dettagli';
              setScanStatus({ status: 'error', message: detail });
              showToast({ type: 'error', title: 'Scan fallito', message: detail });
            } else {
              const found = result?.hosts_found ?? 0;
              setScanStatus({ status: 'completed', message: `Scan completed: ${found} host` });
              loadDiscoveredHosts();
            }
            clearInterval(interval);
          } else if (response.status === 'FAILURE') {
            // Eccezione non gestita nel worker → result è la traceback string
            const rawResult: unknown = (response as unknown as { result?: unknown }).result;
            const errMsg = typeof rawResult === 'string' ? rawResult : 'Scan failed';
            setScanStatus({ status: 'error', message: errMsg });
            showToast({ type: 'error', title: 'Scan fallito', message: errMsg });
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Error polling scan status:', error);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [scanStatus]);

  // ==================== ARP SCAN FUNCTIONS ====================
  
  const loadDiscoveredHosts = async () => {
    try {
      const response = await apiService.getDiscoveredHosts();
      const hosts = Array.isArray(response) ? response : response.results || [];
      setDiscoveredHosts(hosts);
    } catch (error) {
      console.error('Error loading discovered hosts:', error);
    }
  };

  const loadAvailableGroups = async () => {
    try {
      const groupsData = await apiService.getGroups();
      setAvailableGroups(groupsData);
    } catch (error) {
      console.error('Error loading groups:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare i gruppi'
      });
    }
  };

  const handleStartScan = async () => {
    try {
      const response = await apiService.startDiscoveryScan();
      setScanStatus({
        status: 'scanning',
        taskId: response.task_id,
        message: 'Scanning network...'
      });
      showToast({
        type: 'info',
        title: 'Scan started',
        message: 'Network discovery in progress'
      });
    } catch (error) {
      console.error('Error starting scan:', error);
      setScanStatus({ status: 'error', message: 'Failed to start scan' });
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to start network scan'
      });
    }
  };

  const handleToggleHost = (hostId: number) => {
    const newSelected = new Set(selectedHosts);
    if (newSelected.has(hostId)) {
      newSelected.delete(hostId);
    } else {
      newSelected.add(hostId);
    }
    setSelectedHosts(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedHosts.size === discoveredHosts.length) {
      setSelectedHosts(new Set());
    } else {
      const allIds = discoveredHosts.map(h => h.id);  // ✅ Seleziona tutti
      setSelectedHosts(new Set(allIds));
    }
  };

  const handleImportSelected = async () => {
    if (selectedHosts.size === 0) return;

    try {
      setLoading(true);
      
      // ✅ Filtra solo gli host NON già importati
      const hostIds = Array.from(selectedHosts);
      const hostsToImport = discoveredHosts
        .filter(h => hostIds.includes(h.id) && !h.already_target)
        .map(h => h.id);
      
      if (hostsToImport.length === 0) {
        showToast({
          type: 'warning',
          title: 'Nothing to Import',
          message: 'All selected hosts are already imported as targets'
        });
        setLoading(false);
        return;
      }
      
      // Importa solo quelli validi
      for (const hostId of hostsToImport) {
        await apiService.importDiscoveredHost(hostId);
      }
      
      showToast({
        type: 'success',
        title: 'Success',
        message: `Imported ${hostsToImport.length} host(s)`
      });
      
      setSelectedHosts(new Set());
      loadDiscoveredHosts();
    } catch (error) {
      console.error('Error importing hosts:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to import hosts'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSelected = async () => {
    if (selectedHosts.size === 0) return;

    showConfirm({
      title: 'Delete Selected Hosts',
      message: `Are you sure you want to delete ${selectedHosts.size} host(s)? This action cannot be undone.`,
      onConfirm: async () => {
        try {
          setLoading(true);
          
          const hostIds = Array.from(selectedHosts);
          const result = await apiService.bulkDeleteDiscoveredHosts(hostIds);
          
          showToast({
            type: 'success',
            title: 'Success',
            message: result.message || `Deleted ${result.deleted} host(s)`
          });
          
          setSelectedHosts(new Set());
          loadDiscoveredHosts();
        } catch (error: any) {
          console.error('Error deleting hosts:', error);
          showToast({
            type: 'error',
            title: 'Error',
            message: error.response?.data?.error || 'Failed to delete hosts'
          });
        } finally {
          setLoading(false);
        }
      }
    });
  };


  // ==================== FILE IMPORT FUNCTIONS ====================
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setImportFile(e.target.files[0]);
      setImportResult(null);
    }
  };

  const handleFileImport = async () => {
    if (!importFile) {
      showToast({
        type: 'error',
        title: 'No file selected',
        message: 'Please select a file to import'
      });
      return;
    }

    try {
      setLoading(true);
      const result = await apiService.bulkImportFromFile(importFile);
      
      setImportResult(result);
      
      if (result.errors.length === 0) {
        showToast({
          type: 'success',
          title: 'Import completato',
          message: `Importati: ${result.imported} host`
        });
      } else {
        showToast({
          type: 'warning',
          title: 'Import con errori',
          message: `Importati: ${result.imported}, Errori: ${result.errors.length}`
        });
      }
      
      setImportFile(null);
      loadDiscoveredHosts();
    } catch (error) {
      console.error('Error importing file:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile importare il file'
      });
    } finally {
      setLoading(false);
    }
  };

  // ==================== MANUAL ADD FUNCTIONS ====================
  
  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!manualForm.ip_address) {
      showToast({
        type: 'error',
        title: 'Validation Error',
        message: 'IP address is required'
      });
      return;
    }
    if (!manualForm.mac_address) {
      showToast({
        type: 'error',
        title: 'Validation Error',
        message: 'MAC address is required (necessario per l\'identity hash del pairing agent)'
      });
      return;
    }
    if (!/^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$/.test(manualForm.mac_address)) {
      showToast({
        type: 'error',
        title: 'Validation Error',
        message: 'MAC address non valido (formato atteso AA:BB:CC:DD:EE:FF)'
      });
      return;
    }

    try {
      setLoading(true);
      await apiService.createTarget(manualForm);

      showToast({
        type: 'success',
        title: 'Success',
        message: 'Target added successfully'
      });
      
      setManualForm({
        ip_address: '',
        hostname: '',
        mac_address: '',
        description: '',
        group_ids: []
      });
    } catch (error: any) {
      console.error('Error adding target:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.error || 'Failed to add target'
      });
    } finally {
      setLoading(false);
    }
  };

  // ==================== GROUPS FUNCTIONS (NEW) ====================
  
  const loadGroups = async () => {
    try {
      const groups = await apiService.getGroups();
      const list = Array.isArray(groups) ? groups : [];
      setGroups(list);
      // Se l'URL includeva ?group=<id> e il tab è "groups", auto-seleziona
      // quel gruppo per saltare lo step intermedio dell'utente.
      if (groupParam && activeTab === 'groups' && !selectedGroup) {
        const target = list.find((g) => String(g.id) === String(groupParam));
        if (target) handleSelectGroup(target);
      }
    } catch (error) {
      console.error('Error loading groups:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to load groups'
      });
    }
  };

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newGroupForm.name.trim()) {
      showToast({
        type: 'error',
        title: 'Validation Error',
        message: 'Group name is required'
      });
      return;
    }

    try {
      await apiService.createGroup(newGroupForm);
      
      showToast({
        type: 'success',
        title: 'Success',
        message: `Group '${newGroupForm.name}' created`
      });
      
      setNewGroupForm({
        name: '',
        description: '',
        color: '#3b82f6',
        icon: 'server'
      });
      setShowCreateGroup(false);
      loadGroups();
    } catch (error: any) {
      console.error('Error creating group:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.error || 'Failed to create group'
      });
    }
  };

  const handleSelectGroup = async (group: TargetGroup) => {
    try {
      const groupDetails = await apiService.getGroup(group.id);
      setSelectedGroup(groupDetails);

      const availResponse = await apiService.getAvailableTargetsForGroup(group.id);
      setAvailableTargets(availResponse.targets || []);
    } catch (error) {
      console.error('Error loading group details:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: 'Failed to load group details'
      });
    }
  };

  const handleAddTargetToGroup = async (targetId: number) => {
    if (!selectedGroup) return;

    try {
      await apiService.addTargetsToGroup(selectedGroup.id, [targetId]);
      
      showToast({
        type: 'success',
        title: 'Success',
        message: 'Target added to group'
      });
      
      handleSelectGroup(selectedGroup);
      loadGroups();
    } catch (error: any) {
      console.error('Error adding target to group:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.error || 'Failed to add target'
      });
    }
  };

  const handleRemoveTargetFromGroup = async (targetId: number) => {
    if (!selectedGroup) return;

    try {
      await apiService.removeTargetsFromGroup(selectedGroup.id, [targetId]);
      
      showToast({
        type: 'success',
        title: 'Success',
        message: 'Target removed from group'
      });
      
      handleSelectGroup(selectedGroup);
      loadGroups();
    } catch (error: any) {
      console.error('Error removing target from group:', error);
      showToast({
        type: 'error',
        title: 'Error',
        message: error.response?.data?.error || 'Failed to remove target'
      });
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    showConfirm({
      title: 'Delete Group',
      message: 'Are you sure you want to delete this group?',
      onConfirm: async () => {
        try {
          await apiService.deleteGroup(groupId);
          
          showToast({
            type: 'success',
            title: 'Success',
            message: 'Group deleted successfully'
          });
          
          setSelectedGroup(null);
          loadGroups();
        } catch (error: any) {
          console.error('Error deleting group:', error);
          showToast({
            type: 'error',
            title: 'Error',
            message: error.response?.data?.error || 'Failed to delete group'
          });
        }
      }
    });
  };

  // ==================== RENDER ====================

  return (
    <div className="discovery-page">
      {/* Header */}
      <div className="page-header">
        <h1>Network Discovery</h1>
        <div className="header-info">
          <span className="info-badge">
            {discoveredHosts.length} hosts discovered
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="discovery-tabs">
        <button
          className={`tab-button ${activeTab === 'arp-scan' ? 'active' : ''}`}
          onClick={() => setActiveTab('arp-scan')}
        >
          <svg className="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
          </svg>
          ARP Scan
        </button>
        
        <button
          className={`tab-button ${activeTab === 'file' ? 'active' : ''}`}
          onClick={() => setActiveTab('file')}
        >
          <svg className="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
            <polyline points="13 2 13 9 20 9"/>
          </svg>
          File Import
        </button>
        
        <button
          className={`tab-button ${activeTab === 'manual' ? 'active' : ''}`}
          onClick={() => setActiveTab('manual')}
        >
          <svg className="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Manual Add
        </button>

        <button
          className={`tab-button ${activeTab === 'groups' ? 'active' : ''}`}
          onClick={() => setActiveTab('groups')}
        >
          <svg className="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          Groups
        </button>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        
        {/* ==================== ARP-SCAN TAB ==================== */}
        {activeTab === 'arp-scan' && (
          <div className="arp-scan-container">
            {/* Scan Controls */}
            <div className="scan-controls">
              <button
                className="btn-primary btn-scan"
                onClick={handleStartScan}
                disabled={scanStatus.status === 'scanning' || loading}
              >
                {scanStatus.status === 'scanning' ? (
                  <>
                    <span className="spinner"></span>
                    Scanning...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M12 6v6l4 2"/>
                    </svg>
                    Start Network Scan
                  </>
                )}
              </button>

              {scanStatus.message && (
                <div className={`scan-status status-${scanStatus.status}`}>
                  {scanStatus.message}
                </div>
              )}
            </div>

            {/* Discovered Hosts Table */}
            {discoveredHosts.length > 0 && (
              <>
                <div className="table-actions">
                  <button
                    className="btn-secondary"
                    onClick={handleSelectAll}
                  >
                    {selectedHosts.size === discoveredHosts.length ? 'Deselect All' : 'Select All'}
                  </button>
                  
                  <button
                    className="btn-primary"
                    onClick={handleImportSelected}
                    disabled={selectedHosts.size === 0 || loading}
                  >
                    Import Selected ({selectedHosts.size})
                  </button>
                 
                  <button
                    className="btn-delete"
                    onClick={handleDeleteSelected}
                    disabled={selectedHosts.size === 0 || loading}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                    Delete Selected ({selectedHosts.size})
                  </button>
                </div>

                <div className="hosts-table-container">
                  <table className="hosts-table">
                    <thead>
                      <tr>
                        <th className="col-checkbox">
                          <input
                            type="checkbox"
                            checked={selectedHosts.size === discoveredHosts.length}
                            onChange={handleSelectAll}
                          />
                        </th>
                        <th>IP Address</th>
                        <th>MAC Address</th>
                        <th>Hostname</th>
                        <th>Vendor</th>
                        <th>Last Seen</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {discoveredHosts.map((host) => (
                        <tr
                          key={host.id}
                              className={`
                                ${selectedHosts.has(host.id) ? 'selected' : ''}
                                ${host.already_target ? 'already-imported' : ''}
                              `}
                            >
                          <td className="col-checkbox">
                            <input
                              type="checkbox"
                              checked={selectedHosts.has(host.id)}
                              onChange={() => handleToggleHost(host.id)}
                            />
                          </td>
                          <td className="col-ip">{host.ip_address}</td>
                          <td className="col-mac">{host.mac_address}</td>
                          <td>{host.hostname || '-'}</td>
                          <td className="col-vendor">{host.vendor || '-'}</td>
                          <td>{new Date(host.last_seen).toLocaleString()}</td>
                          <td>
                            {host.already_target ? (
                              <span className="badge badge-info">Already Target</span>
                            ) : host.is_imported ? (
                              <span className="badge badge-success">Imported</span>
                            ) : (
                              <span className="badge badge-warning">New</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {discoveredHosts.length === 0 && scanStatus.status === 'idle' && (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 6v6l4 2"/>
                </svg>
                <p>No hosts discovered yet</p>
                <p className="empty-subtitle">Start a network scan to discover devices</p>
              </div>
            )}
          </div>
        )}

        {/* ==================== FILE IMPORT TAB ==================== */}
        {activeTab === 'file' && (
          <div className="file-import-container">
            <div className="import-card">
              <h2>Bulk Import from File</h2>
              <p className="import-description">
                Upload a text file with one host per line.<br/>
                Format raccomandato: <code>IP_ADDRESS MAC_ADDRESS HOSTNAME [DESCRIPTION]</code><br/>
                <small>(senza MAC il target è importato ma non può completare il pairing dell'agent finché non lo aggiungi a mano)</small>
              </p>

              <div className="file-format-example">
                <h3>Example File:</h3>
                <pre>
{`192.168.1.100 AA:BB:CC:11:22:33 server01 Production web server
192.168.1.101 AA:BB:CC:11:22:44 server02 Database server
192.168.1.102 AA:BB:CC:11:22:55 server03 Backup server

# Formato legacy (senza MAC, ancora supportato ma sconsigliato):
192.168.1.103 server04 Legacy host`}
                </pre>
              </div>

              <div className="file-input-group">
                <input
                  type="file"
                  accept=".txt"
                  onChange={handleFileChange}
                  id="import-file"
                  className="file-input"
                />
                <label htmlFor="import-file" className="file-label">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                  {importFile ? importFile.name : 'Choose File'}
                </label>
              </div>

              <button
                className="btn-primary"
                onClick={handleFileImport}
                disabled={!importFile || loading}
              >
                {loading ? 'Importing...' : 'Import File'}
              </button>

              {importResult && (
                <div className="import-result">
                  <h3>Import Results:</h3>
                  <div className="result-stats">
                    <div className="stat-item stat-success">
                      <span className="stat-label">Imported:</span>
                      <span className="stat-value">{importResult.imported}</span>
                    </div>
                    <div className="stat-item stat-warning">
                      <span className="stat-label">Skipped:</span>
                      <span className="stat-value">{importResult.skipped}</span>
                    </div>
                    <div className="stat-item stat-error">
                      <span className="stat-label">Errors:</span>
                      <span className="stat-value">{importResult.errors.length}</span>
                    </div>
                  </div>

                  {importResult.errors.length > 0 && (
                    <div className="error-list">
                      <h4>Errors:</h4>
                      {importResult.errors.map((err, idx) => (
                        <div key={idx} className="error-item">
                          <span className="error-line">Line {err.line}:</span>
                          <span className="error-msg">{err.error}</span>
                          <code className="error-content">{err.content}</code>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================== MANUAL ADD TAB ==================== */}
        {activeTab === 'manual' && (
          <div className="manual-add-container">
            <div className="manual-card">
              <h2>Add Target Manually</h2>
              <p className="manual-description">
                Enter target details to add it to your managed systems
              </p>

              <form onSubmit={handleManualSubmit} className="manual-form">
                <div className="form-group">
                  <label htmlFor="ip_address">IP Address *</label>
                  <input
                    type="text"
                    id="ip_address"
                    value={manualForm.ip_address}
                    onChange={(e) => setManualForm({...manualForm, ip_address: e.target.value})}
                    placeholder="192.168.1.100"
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="hostname">Hostname</label>
                  <input
                    type="text"
                    id="hostname"
                    value={manualForm.hostname}
                    onChange={(e) => setManualForm({...manualForm, hostname: e.target.value})}
                    placeholder="server.local"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="mac_address">MAC Address *</label>
                  <input
                    type="text"
                    id="mac_address"
                    value={manualForm.mac_address}
                    onChange={(e) => setManualForm({...manualForm, mac_address: e.target.value})}
                    placeholder="AA:BB:CC:DD:EE:FF"
                    pattern="^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
                    required
                  />
                  <small className="form-hint">Necessario per l'identity hash usato dal pairing dell'agent</small>
                </div>

                <div className="form-group">
                  <label htmlFor="description">Description</label>
                  <textarea
                    id="description"
                    value={manualForm.description}
                    onChange={(e) => setManualForm({...manualForm, description: e.target.value})}
                    placeholder="Server description..."
                    rows={3}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="groups">Gruppi (seleziona uno o più)</label>
                  <select
                    id="groups"
                    multiple
                    value={manualForm.group_ids?.map(String) || []}
                    onChange={(e) => {
                      const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                      setManualForm({...manualForm, group_ids: selected});
                    }}
                    style={{ minHeight: '120px' }}
                  >
                    {availableGroups.map(group => (
                      <option key={group.id} value={group.id}>{group.name}</option>
                    ))}
                  </select>
                  <small className="form-hint">Tieni premuto Ctrl (Cmd su Mac) per selezionare più gruppi. Assegna il target a uno o più gruppi per gestione regole centralizzata.</small>
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading || !manualForm.ip_address || !manualForm.mac_address}
                >
                  {loading ? 'Adding...' : 'Add Target'}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ==================== GROUPS TAB (NEW) ==================== */}
        {activeTab === 'groups' && (
          <div className="groups-container">
            <div className="groups-layout">
              {/* Sidebar: Groups List */}
              <div className="groups-sidebar">
                <div className="sidebar-header">
                  <h3>Groups</h3>
                  <button
                    className="btn-create-group"
                    onClick={() => setShowCreateGroup(true)}
                    title="Create new group"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <line x1="12" y1="5" x2="12" y2="19"/>
                      <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                  </button>
                </div>

                <div className="groups-list">
                  {groups.length === 0 ? (
                    <div className="empty-state-small">
                      <p>No groups yet</p>
                      <button
                        className="btn-link"
                        onClick={() => setShowCreateGroup(true)}
                      >
                        Create your first group
                      </button>
                    </div>
                  ) : (
                    groups.map((group) => (
                      <div
                        key={group.id}
                        className={`group-item ${selectedGroup?.id === group.id ? 'active' : ''}`}
                        onClick={() => handleSelectGroup(group)}
                      >
                        <div
                          className="group-color"
                          style={{ backgroundColor: group.color }}
                        />
                        <div className="group-info">
                          <h4>{group.name}</h4>
                          <span className="group-count">{group.target_count} targets</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Main Content: Group Details */}
              <div className="groups-main">
                {selectedGroup ? (
                  <>
                    {/* Group Header */}
                    <div className="group-header">
                      <div className="group-title">
                        <div
                          className="group-badge"
                          style={{ backgroundColor: selectedGroup.color }}
                        />
                        <div>
                          <h2>{selectedGroup.name}</h2>
                          <p>{selectedGroup.description || 'No description'}</p>
                        </div>
                      </div>
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteGroup(selectedGroup.id)}
                        title="Delete group"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <polyline points="3 6 5 6 21 6"/>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                      </button>
                    </div>

                    {/* Target Assignment */}
                    <div className="target-assignment">
                      {/* Available Targets */}
                      <div className="target-panel">
                        <h3>Available Targets</h3>
                        <div className="target-list">
                          {availableTargets.length === 0 ? (
                            <div className="empty-state-small">
                              <p>All targets assigned</p>
                            </div>
                          ) : (
                            availableTargets.map((target) => (
                              <div key={target.id} className="target-card">
                                <div className="target-info">
                                  <span className={`status-dot status-${target.status}`}/>
                                  <div>
                                    <p className="target-ip">{target.ip_address}</p>
                                    <p className="target-hostname">{target.hostname || 'No hostname'}</p>
                                  </div>
                                </div>
                                <button
                                  className="btn-add-target"
                                  onClick={() => handleAddTargetToGroup(target.id)}
                                  title="Add to group"
                                >
                                  →
                                </button>
                              </div>
                            ))
                          )}
                        </div>
                      </div>

                      {/* Group Targets */}
                      <div className="target-panel">
                        <h3>Group Members</h3>
                        <div className="target-list">
                          {!selectedGroup.targets || selectedGroup.targets.length === 0 ? (
                            <div className="empty-state-small">
                              <p>No targets in group</p>
                            </div>
                          ) : (
                            selectedGroup.targets.map((target) => (
                              <div key={target.id} className="target-card target-in-group">
                                <div className="target-info">
                                  <span className={`status-dot status-${target.status}`}/>
                                  <div>
                                    <p className="target-ip">{target.ip_address}</p>
                                    <p className="target-hostname">{target.hostname || 'No hostname'}</p>
                                  </div>
                                </div>
                                <button
                                  className="btn-remove-target"
                                  onClick={() => handleRemoveTargetFromGroup(target.id)}
                                  title="Remove from group"
                                >
                                  ×
                                </button>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                      <circle cx="9" cy="7" r="4"/>
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                    </svg>
                    <p>Select a Group</p>
                    <p className="empty-subtitle">
                      Choose a group from the sidebar to view and manage its targets
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Create Group Modal */}
      {showCreateGroup && (
        <div className="modal-overlay" onClick={() => setShowCreateGroup(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Group</h2>
              <button
                className="modal-close"
                onClick={() => setShowCreateGroup(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateGroup} className="modal-form">
              <div className="form-group">
                <label htmlFor="group_name">Group Name *</label>
                <input
                  type="text"
                  id="group_name"
                  value={newGroupForm.name}
                  onChange={(e) => setNewGroupForm({...newGroupForm, name: e.target.value})}
                  placeholder="Web Servers"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="group_description">Description</label>
                <textarea
                  id="group_description"
                  value={newGroupForm.description}
                  onChange={(e) => setNewGroupForm({...newGroupForm, description: e.target.value})}
                  placeholder="Describe the purpose of this group..."
                  rows={3}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="group_color">Color</label>
                  <input
                    type="color"
                    id="group_color"
                    value={newGroupForm.color}
                    onChange={(e) => setNewGroupForm({...newGroupForm, color: e.target.value})}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="group_icon">Icon</label>
                  <select
                    id="group_icon"
                    value={newGroupForm.icon}
                    onChange={(e) => setNewGroupForm({...newGroupForm, icon: e.target.value})}
                  >
                    <option value="server">Server</option>
                    <option value="database">Database</option>
                    <option value="globe">Web/DNS</option>
                    <option value="shield">Security</option>
                    <option value="storage">Storage</option>
                  </select>
                </div>
              </div>

              <div className="modal-actions">
                <button type="submit" className="btn-primary">
                  Create Group
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateGroup(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Discovery;
