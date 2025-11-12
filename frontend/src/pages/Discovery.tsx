/**
 * Discovery Page - Network Discovery e Import Target
 * 
 * 3 Modalità:
 * 1. ARP-Scan Network Discovery
 * 2. Bulk Import da File
 * 3. Aggiunta Manuale
 */
import React, { useState, useEffect } from 'react';
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

const Discovery: React.FC = () => {
  // State
  const [activeTab, setActiveTab] = useState<'arp-scan' | 'file' | 'manual'>('arp-scan');
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
    description: ''
  });

  // Load discovered hosts on mount
  useEffect(() => {
    loadDiscoveredHosts();
  }, []);

  // Poll scan status
  useEffect(() => {
    if (scanStatus.status === 'scanning' && scanStatus.taskId) {
      const interval = setInterval(async () => {
        try {
          const response = await apiService.getDiscoveryScanStatus(scanStatus.taskId!);
          
          if (response.status === 'SUCCESS') {
            setScanStatus({ status: 'completed', message: 'Scan completed' });
            loadDiscoveredHosts();
            clearInterval(interval);
          } else if (response.status === 'FAILURE') {
            setScanStatus({ status: 'error', message: 'Scan failed' });
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Error polling scan status:', error);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [scanStatus]);

  const loadDiscoveredHosts = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Chiamata API reale
      const response = await api.get<{
        count: number;
        results: DiscoveredHost[];
      }>('/api/discovery/get_results/?not_imported=true');
      
      console.log('API Response:', response.data);
      console.log('Found hosts:', response.data.count);
      
      // Usa i dati reali dall'API
      setHosts(response.data.results);
      
    } catch (err) {
      console.error('Error loading discovered hosts:', err);
      setError('Failed to load discovered hosts');
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to load discovered hosts'
      });
    } finally {
      setLoading(false);
    }
  };

  // ==================== ARP-SCAN ====================
  
  const handleStartScan = async () => {
    try {
      setScanStatus({ status: 'scanning', message: 'Starting network scan...' });
      const response = await apiService.startDiscoveryScan();
      
      setScanStatus({
        status: 'scanning',
        taskId: response.task_id,
        message: 'Scanning network...'
      });
    } catch (error) {
      console.error('Error starting scan:', error);
      setScanStatus({ status: 'error', message: 'Failed to start scan' });
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
      setSelectedHosts(new Set(discoveredHosts.map(h => h.id)));
    }
  };

  const handleImportSelected = async () => {
    if (selectedHosts.size === 0) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Seleziona almeno un host da importare'
      });
      return;
    }

    showConfirm({
      title: 'Conferma Import',
      message: `Vuoi importare ${selectedHosts.size} host come target?`,
      confirmText: 'Importa',
      cancelText: 'Annulla',
      onConfirm: async () => {
        try {
          setLoading(true);
          const hostIds = Array.from(selectedHosts);
          const result = await apiService.bulkImportDiscoveredHosts(hostIds);
          
          showToast({
            type: 'success',
            title: 'Import completato',
            message: `Importati: ${result.imported}, Saltati: ${result.skipped}`
          });
          
          setSelectedHosts(new Set());
          loadDiscoveredHosts();
        } catch (error) {
          console.error('Error importing hosts:', error);
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile importare gli host'
          });
        } finally {
          setLoading(false);
        }
      }
    });
  };

  // ==================== FILE IMPORT ====================
  
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setImportFile(e.target.files[0]);
      setImportResult(null);
    }
  };

  const handleFileImport = async () => {
    if (!importFile) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Seleziona un file da importare'
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

  // ==================== MANUAL ADD ====================
  
  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!manualForm.ip_address) {
      alert('IP address is required');
      return;
    }

    try {
      setLoading(true);
      await apiService.createTarget(manualForm);
      
      alert('Target added successfully');
      
      setManualForm({
        ip_address: '',
        hostname: '',
        description: ''
      });
    } catch (error: any) {
      console.error('Error adding target:', error);
      alert(error.response?.data?.error || 'Failed to add target');
    } finally {
      setLoading(false);
    }
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
                          className={selectedHosts.has(host.id) ? 'selected' : ''}
                        >
                          <td className="col-checkbox">
                            <input
                              type="checkbox"
                              checked={selectedHosts.has(host.id)}
                              onChange={() => handleToggleHost(host.id)}
                              disabled={host.already_target}
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
                Format: <code>IP_ADDRESS HOSTNAME [DESCRIPTION]</code>
              </p>

              <div className="file-format-example">
                <h3>Example File:</h3>
                <pre>
{`192.168.1.100 server01 Production web server
192.168.1.101 server02 Database server
192.168.1.102 server03 Backup server`}
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
                    <div className="import-errors">
                      <h4>Errors:</h4>
                      {importResult.errors.map((err, idx) => (
                        <div key={idx} className="error-item">
                          <span className="error-line">Line {err.line}:</span>
                          <span className="error-message">{err.error}</span>
                          <code>{err.content}</code>
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
                Add a single target by entering its details
              </p>

              <form onSubmit={handleManualSubmit} className="manual-form">
                <div className="form-group">
                  <label htmlFor="ip_address">IP Address *</label>
                  <input
                    id="ip_address"
                    type="text"
                    className="input"
                    placeholder="192.168.1.100"
                    value={manualForm.ip_address}
                    onChange={(e) => setManualForm({ ...manualForm, ip_address: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="hostname">Hostname</label>
                  <input
                    id="hostname"
                    type="text"
                    className="input"
                    placeholder="server01"
                    value={manualForm.hostname}
                    onChange={(e) => setManualForm({ ...manualForm, hostname: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="description">Description</label>
                  <textarea
                    id="description"
                    className="input textarea"
                    placeholder="Optional description..."
                    value={manualForm.description}
                    onChange={(e) => setManualForm({ ...manualForm, description: e.target.value })}
                    rows={3}
                  />
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading}
                >
                  {loading ? 'Adding...' : 'Add Target'}
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Discovery;
