/**
 * Targets Management Page
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target, TargetCreate } from '../types';
import './Targets.css';

const Targets: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
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
      loadTargets();
    } catch (error) {
      console.error('Error creating target:', error);
    }
  };

  const handleTestConnection = async (id: number) => {
    try {
      const result = await apiService.testConnection(id);
      alert(result.success ? 'Connection successful!' : `Connection failed: ${result.error}`);
      loadTargets();
    } catch (error) {
      alert('Connection test failed');
    }
  };

  const handleInstall = async (id: number) => {
    if (!window.confirm('Install FireDog on this target?')) return;
    try {
      await apiService.installFiredog(id);
      alert('Installation started. Check logs for progress.');
      loadTargets();
    } catch (error) {
      console.error('Error installing:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this target?')) return;
    try {
      await apiService.deleteTarget(id);
      loadTargets();
    } catch (error) {
      console.error('Error deleting:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return '#26de81';
      case 'offline': return '#ff4757';
      case 'error': return '#ff6348';
      case 'installing': return '#ffa502';
      default: return '#a4b0be';
    }
  };

  if (loading) return <div className="loading">Loading targets...</div>;

  return (
    <div className="targets-page">
      <div className="page-header">
        <h1>Targets Management</h1>
        <button onClick={() => setShowModal(true)} className="btn-primary">
          + Add Target
        </button>
      </div>

      <div className="targets-grid">
        {targets.map(target => (
          <div key={target.id} className="target-card">
            <div className="target-header">
              <h3>{target.hostname || target.ip_address}</h3>
              <span className="status-badge" style={{ background: getStatusColor(target.status) }}>
                {target.status}
              </span>
            </div>
            
            <div className="target-info">
              <div className="info-item">
                <span className="label">IP:</span>
                <span className="value">{target.ip_address}</span>
              </div>
              <div className="info-item">
                <span className="label">Version:</span>
                <span className="value">{target.firedog_version || 'N/A'}</span>
              </div>
              <div className="info-item">
                <span className="label">Last Seen:</span>
                <span className="value">
                  {target.last_seen ? new Date(target.last_seen).toLocaleString() : 'Never'}
                </span>
              </div>
            </div>

            <div className="target-actions">
              <button onClick={() => handleTestConnection(target.id)} className="btn-small">
                Test
              </button>
              {target.status !== 'online' && (
                <button onClick={() => handleInstall(target.id)} className="btn-small btn-success">
                  Install
                </button>
              )}
              <button onClick={() => handleDelete(target.id)} className="btn-small btn-danger">
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h2>Add New Target</h2>
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>IP Address *</label>
                <input
                  type="text"
                  value={formData.ip_address}
                  onChange={e => setFormData({...formData, ip_address: e.target.value})}
                  required
                />
              </div>
              <div className="form-group">
                <label>Hostname</label>
                <input
                  type="text"
                  value={formData.hostname}
                  onChange={e => setFormData({...formData, hostname: e.target.value})}
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={e => setFormData({...formData, description: e.target.value})}
                />
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Create
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
