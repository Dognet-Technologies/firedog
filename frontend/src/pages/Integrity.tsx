import React, { useState, useEffect } from 'react';
import integrityService, { FileIntegrity, IntegrityStats, IntegrityFilter } from '../services/integrity.service';
import './Integrity.css';

const Integrity: React.FC = () => {
  const [files, setFiles] = useState<FileIntegrity[]>([]);
  const [stats, setStats] = useState<IntegrityStats | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Filtri
  const [filters, setFilters] = useState<IntegrityFilter>({
    status: undefined,
    limit: 50,
  });

  // Modal approvazione
  const [showApproveModal, setShowApproveModal] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<FileIntegrity | null>(null);
  const [approvalNotes, setApprovalNotes] = useState<string>('');

  // Modal dettaglio
  const [showDetailModal, setShowDetailModal] = useState<boolean>(false);

  useEffect(() => {
    loadFiles();
    loadStats();
  }, []);

  const loadFiles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await integrityService.getFiles(filters);
      setFiles(data.results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await integrityService.getStats();
      setStats(data);
    } catch (err: any) {
      console.error('Error loading stats:', err);
    }
  };

  const handleCheckIntegrity = async () => {
    if (!window.confirm('Eseguire il check di integrità su tutti i file monitorati?')) {
      return;
    }

    setChecking(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await integrityService.checkIntegrity();
      if (result.violations > 0) {
        setError(`Rilevate ${result.violations} violazioni su ${result.checked_files} file`);
      } else {
        setSuccess(`Tutti i ${result.checked_files} file sono OK`);
      }
      await loadFiles();
      await loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setChecking(false);
    }
  };

  const openApproveModal = (file: FileIntegrity) => {
    setSelectedFile(file);
    setShowApproveModal(true);
    setApprovalNotes('');
    setError(null);
  };

  const handleApprove = async () => {
    if (!selectedFile) return;

    if (!approvalNotes.trim()) {
      setError('Inserire una nota per l\'approvazione');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await integrityService.approveChange(selectedFile.id, approvalNotes);
      setSuccess(`Modifica approvata per ${selectedFile.file_path}`);
      setShowApproveModal(false);
      await loadFiles();
      await loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openDetailModal = (file: FileIntegrity) => {
    setSelectedFile(file);
    setShowDetailModal(true);
  };

  const handleFilterChange = (key: keyof IntegrityFilter, value: any) => {
    setFilters({ ...filters, [key]: value });
  };

  const applyFilters = () => {
    loadFiles();
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'ok':
        return '#7dffaa';
      case 'modified':
        return '#ff9500';
      case 'missing':
        return '#ff4d4d';
      case 'new':
        return '#00c9ff';
      default:
        return '#8e91a1';
    }
  };

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'ok':
        return '✓';
      case 'modified':
        return '⚠';
      case 'missing':
        return '✗';
      case 'new':
        return '+';
      default:
        return '?';
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const truncateHash = (hash: string): string => {
    if (!hash || hash.length < 16) return hash;
    return `${hash.substring(0, 8)}...${hash.substring(hash.length - 8)}`;
  };

  return (
    <div className="integrity-page">
      {/* Header */}
      <div className="page-header">
        <div className="header-left">
          <h1>File Integrity Monitoring</h1>
          <p className="subtitle">Monitoraggio integrità file critici (SHA512)</p>
        </div>
        <div className="header-actions">
          <button
            className="btn-check"
            onClick={handleCheckIntegrity}
            disabled={checking || loading}
          >
            {checking ? '🔄 Checking...' : '🔍 Check Integrity'}
          </button>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="alert alert-error">
          <strong>Errore:</strong> {error}
          <button className="alert-close" onClick={() => setError(null)}>×</button>
        </div>
      )}
      
      {success && (
        <div className="alert alert-success">
          <strong>Successo:</strong> {success}
          <button className="alert-close" onClick={() => setSuccess(null)}>×</button>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_files}</div>
            <div className="stat-label">File Monitorati</div>
          </div>
          <div className="stat-card ok">
            <div className="stat-value">{stats.ok_files}</div>
            <div className="stat-label">OK</div>
          </div>
          <div className="stat-card modified">
            <div className="stat-value">{stats.modified_files}</div>
            <div className="stat-label">Modificati</div>
          </div>
          <div className="stat-card missing">
            <div className="stat-value">{stats.missing_files}</div>
            <div className="stat-label">Mancanti</div>
          </div>
          <div className="stat-card new">
            <div className="stat-value">{stats.new_files}</div>
            <div className="stat-label">Nuovi</div>
          </div>
          <div className="stat-card pending">
            <div className="stat-value">{stats.pending_approval}</div>
            <div className="stat-label">Da Approvare</div>
          </div>
        </div>
      )}

      {/* Filtri */}
      <div className="filters-section">
        <h3>Filtri</h3>
        <div className="filters-grid">
          <div className="filter-group">
            <label>Status</label>
            <select
              value={filters.status || ''}
              onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
              className="filter-select"
            >
              <option value="">Tutti</option>
              <option value="ok">OK</option>
              <option value="modified">Modificati</option>
              <option value="missing">Mancanti</option>
              <option value="new">Nuovi</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Approvazione</label>
            <select
              value={filters.is_change_approved === undefined ? '' : filters.is_change_approved ? 'approved' : 'pending'}
              onChange={(e) => {
                const value = e.target.value;
                handleFilterChange('is_change_approved', value === '' ? undefined : value === 'approved');
              }}
              className="filter-select"
            >
              <option value="">Tutti</option>
              <option value="approved">Approvati</option>
              <option value="pending">Da Approvare</option>
            </select>
          </div>

          <div className="filter-group">
            <label>Tipo File</label>
            <input
              type="text"
              placeholder="es. python, config"
              value={filters.file_type || ''}
              onChange={(e) => handleFilterChange('file_type', e.target.value || undefined)}
              className="filter-input"
            />
          </div>
        </div>
        <button className="btn-apply-filters" onClick={applyFilters} disabled={loading}>
          {loading ? 'Caricamento...' : 'Applica Filtri'}
        </button>
      </div>

      {/* Files Table */}
      <div className="files-section">
        <h3>File Monitorati</h3>
        {loading && files.length === 0 ? (
          <div className="loading-spinner">Caricamento file...</div>
        ) : files.length === 0 ? (
          <div className="no-data">Nessun file trovato</div>
        ) : (
          <div className="table-container">
            <table className="files-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>File Path</th>
                  <th>Tipo</th>
                  <th>Dimensione</th>
                  <th>Hash SHA512</th>
                  <th>Ultimo Check</th>
                  <th>Approvato</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file) => (
                  <tr key={file.id} className={file.status !== 'ok' ? 'warning-row' : ''}>
                    <td>
                      <span
                        className="status-badge"
                        style={{
                          background: `${getStatusColor(file.status)}33`,
                          color: getStatusColor(file.status),
                          border: `1px solid ${getStatusColor(file.status)}66`
                        }}
                      >
                        {getStatusIcon(file.status)} {file.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="path-cell" title={file.file_path}>
                      {file.file_path}
                    </td>
                    <td>
                      <span className="type-badge">{file.file_type || 'unknown'}</span>
                    </td>
                    <td>{formatFileSize(file.file_size)}</td>
                    <td className="hash-cell" title={file.sha512_hash}>
                      {truncateHash(file.sha512_hash)}
                    </td>
                    <td className="date-cell">{formatDate(file.last_checked)}</td>
                    <td>
                      {file.is_change_approved ? (
                        <span className="approved-badge">✓ Sì</span>
                      ) : (
                        <span className="pending-badge">⏳ No</span>
                      )}
                    </td>
                    <td className="actions-cell">
                      <button
                        className="btn-detail"
                        onClick={() => openDetailModal(file)}
                      >
                        Dettagli
                      </button>
                      {file.status === 'modified' && !file.is_change_approved && (
                        <button
                          className="btn-approve"
                          onClick={() => openApproveModal(file)}
                          disabled={loading}
                        >
                          Approva
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Approve Modal */}
      {showApproveModal && selectedFile && (
        <div className="modal-overlay" onClick={() => setShowApproveModal(false)}>
          <div className="modal-content approve-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Approva Modifica File</h3>
              <button className="modal-close" onClick={() => setShowApproveModal(false)}>×</button>
            </div>
            
            <div className="modal-body">
              <div className="warning-box">
                <strong>⚠ Attenzione:</strong> Stai per approvare la modifica di un file critico.
                Assicurati che la modifica sia legittima prima di procedere.
              </div>

              <div className="file-info">
                <div className="info-row">
                  <span className="info-label">File:</span>
                  <span className="info-value">{selectedFile.file_path}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Hash Precedente:</span>
                  <span className="info-value hash-value">{truncateHash(selectedFile.previous_hash)}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Hash Corrente:</span>
                  <span className="info-value hash-value">{truncateHash(selectedFile.sha512_hash)}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Rilevata:</span>
                  <span className="info-value">{selectedFile.change_detected_at ? formatDate(selectedFile.change_detected_at) : 'N/A'}</span>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="approval-notes">Note Approvazione *</label>
                <textarea
                  id="approval-notes"
                  rows={4}
                  required
                  value={approvalNotes}
                  onChange={(e) => setApprovalNotes(e.target.value)}
                  className="form-textarea"
                  placeholder="Inserisci il motivo dell'approvazione (es. update legittimo del sistema, patch di sicurezza, ecc.)"
                />
              </div>
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowApproveModal(false)}
                disabled={loading}
              >
                Annulla
              </button>
              <button
                className="btn-approve-confirm"
                onClick={handleApprove}
                disabled={loading || !approvalNotes.trim()}
              >
                {loading ? 'Approvazione...' : '✓ Approva Modifica'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {showDetailModal && selectedFile && (
        <div className="modal-overlay" onClick={() => setShowDetailModal(false)}>
          <div className="modal-content detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Dettagli File</h3>
              <button className="modal-close" onClick={() => setShowDetailModal(false)}>×</button>
            </div>
            
            <div className="detail-body">
              <div className="detail-row">
                <span className="detail-label">Path Completo:</span>
                <span className="detail-value path-value">{selectedFile.file_path}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Tipo:</span>
                <span className="detail-value">{selectedFile.file_type || 'N/A'}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Status:</span>
                <span
                  className="status-badge"
                  style={{
                    background: `${getStatusColor(selectedFile.status)}33`,
                    color: getStatusColor(selectedFile.status),
                    border: `1px solid ${getStatusColor(selectedFile.status)}66`
                  }}
                >
                  {getStatusIcon(selectedFile.status)} {selectedFile.status.toUpperCase()}
                </span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Dimensione:</span>
                <span className="detail-value">{formatFileSize(selectedFile.file_size)}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Permessi:</span>
                <span className="detail-value">{selectedFile.file_permissions || 'N/A'}</span>
              </div>

              <div className="detail-row">
                <span className="detail-label">Proprietario:</span>
                <span className="detail-value">{selectedFile.file_owner || 'N/A'}</span>
              </div>

              <div className="detail-row full-width">
                <span className="detail-label">Hash SHA512:</span>
                <div className="hash-box">{selectedFile.sha512_hash}</div>
              </div>

              {selectedFile.previous_hash && (
                <div className="detail-row full-width">
                  <span className="detail-label">Hash Precedente:</span>
                  <div className="hash-box">{selectedFile.previous_hash}</div>
                </div>
              )}

              <div className="detail-row">
                <span className="detail-label">Ultimo Check:</span>
                <span className="detail-value">{formatDate(selectedFile.last_checked)}</span>
              </div>

              {selectedFile.change_detected_at && (
                <div className="detail-row">
                  <span className="detail-label">Modifica Rilevata:</span>
                  <span className="detail-value">{formatDate(selectedFile.change_detected_at)}</span>
                </div>
              )}

              <div className="detail-row">
                <span className="detail-label">Approvato:</span>
                {selectedFile.is_change_approved ? (
                  <span className="approved-badge">✓ Sì</span>
                ) : (
                  <span className="pending-badge">⏳ No</span>
                )}
              </div>

              {selectedFile.approved_by && (
                <>
                  <div className="detail-row">
                    <span className="detail-label">Approvato Da:</span>
                    <span className="detail-value">{selectedFile.approved_by}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Data Approvazione:</span>
                    <span className="detail-value">{selectedFile.approved_at ? formatDate(selectedFile.approved_at) : 'N/A'}</span>
                  </div>
                </>
              )}

              {selectedFile.change_notes && (
                <div className="detail-row full-width">
                  <span className="detail-label">Note:</span>
                  <div className="notes-box">{selectedFile.change_notes}</div>
                </div>
              )}
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowDetailModal(false)}
              >
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Integrity;
