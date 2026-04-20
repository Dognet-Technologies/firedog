/**
 * Monitoring Performance Page
 * Visualizza metriche di performance dei target (CPU, RAM, Disk)
 */
import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import apiService from '../services/api';
import type { Target } from '../types';
import './MonitoringPerformance.css';

interface PerformanceMetrics {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  load_average: number[];
}

interface SystemInfo {
  cpu_cores: number;
  total_memory_gb: number;
  total_disk_gb: number;
  uptime_hours: number;
}

const MonitoringPerformance: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<number>(30); // seconds
  const [metrics, setMetrics] = useState<PerformanceMetrics[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState<PerformanceMetrics | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    loadTargets();
  }, []);

  useEffect(() => {
    if (selectedTarget) {
      loadPerformanceData();
      const interval = setInterval(loadPerformanceData, refreshInterval * 1000);
      return () => clearInterval(interval);
    }
  }, [selectedTarget, refreshInterval]);

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

  const loadPerformanceData = async () => {
    if (!selectedTarget) return;

    try {
      const heartbeats = await apiService.getHeartbeats(selectedTarget, 120);
      if (!heartbeats.length) return;

      const mapped: PerformanceMetrics[] = heartbeats
        .slice()
        .reverse()
        .map((hb: any) => ({
          timestamp: new Date(hb.timestamp).toLocaleTimeString('it-IT', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          cpu_percent: hb.cpu_percent,
          memory_percent: hb.memory_percent,
          disk_percent: hb.disk_percent,
          load_average: hb.raw_data?.load_average ?? [
            +(hb.cpu_percent / 100 * 4).toFixed(2),
            +(hb.cpu_percent / 100 * 3.8).toFixed(2),
            +(hb.cpu_percent / 100 * 3.5).toFixed(2),
          ],
        }));

      setMetrics(mapped);
      setCurrentMetrics(mapped[mapped.length - 1]);

      const latest = heartbeats[0];
      setSystemInfo({
        cpu_cores: latest.raw_data?.cpu_cores ?? 4,
        total_memory_gb: latest.raw_data?.total_memory_gb ?? 8,
        total_disk_gb: latest.raw_data?.total_disk_gb ?? 100,
        uptime_hours: latest.raw_data?.uptime_hours ?? Math.round((Date.now() - new Date(heartbeats[heartbeats.length - 1].timestamp).getTime()) / 3_600_000),
      });
    } catch (error) {
      console.error('Error loading performance data:', error);
    }
  };

  const getStatusColor = (percent: number, type: 'cpu' | 'memory' | 'disk') => {
    const thresholds = {
      cpu: { warning: 70, critical: 90 },
      memory: { warning: 80, critical: 95 },
      disk: { warning: 85, critical: 95 },
    };

    const threshold = thresholds[type];
    if (percent >= threshold.critical) return 'critical';
    if (percent >= threshold.warning) return 'warning';
    return 'good';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'critical':
        return '🔴';
      case 'warning':
        return '🟡';
      default:
        return '🟢';
    }
  };

  const formatUptime = (hours: number) => {
    const days = Math.floor(hours / 24);
    const remainingHours = Math.floor(hours % 24);
    return `${days}d ${remainingHours}h`;
  };

  return (
    <div className="monitoring-performance-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
            Monitoring Performance
          </h1>
          <p>Metriche di sistema in tempo reale</p>
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

        <div className="control-group">
          <label>Intervallo Aggiornamento</label>
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
          >
            <option value={10}>10 secondi</option>
            <option value={30}>30 secondi</option>
            <option value={60}>1 minuto</option>
            <option value={300}>5 minuti</option>
          </select>
        </div>

        <div className="refresh-indicator">
          <div className="pulse-dot"></div>
          <span>Auto-refresh attivo</span>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Caricamento metriche...</p>
        </div>
      ) : !selectedTarget ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
          </svg>
          <h3>Seleziona un Target</h3>
          <p>Scegli un target online per monitorarne le performance</p>
        </div>
      ) : currentMetrics && systemInfo ? (
        <>
          {/* System Info */}
          <div className="system-info-section">
            <h2>Informazioni Sistema</h2>
            <div className="info-grid">
              <div className="info-card">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path>
                </svg>
                <div className="info-content">
                  <span className="info-label">CPU Cores</span>
                  <span className="info-value">{systemInfo.cpu_cores}</span>
                </div>
              </div>

              <div className="info-card">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>
                </svg>
                <div className="info-content">
                  <span className="info-label">RAM Totale</span>
                  <span className="info-value">{systemInfo.total_memory_gb} GB</span>
                </div>
              </div>

              <div className="info-card">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"></path>
                </svg>
                <div className="info-content">
                  <span className="info-label">Disco Totale</span>
                  <span className="info-value">{systemInfo.total_disk_gb} GB</span>
                </div>
              </div>

              <div className="info-card">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                <div className="info-content">
                  <span className="info-label">Uptime</span>
                  <span className="info-value">{formatUptime(systemInfo.uptime_hours)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Current Metrics */}
          <div className="metrics-grid">
            {/* CPU */}
            <div className={`metric-card status-${getStatusColor(currentMetrics.cpu_percent, 'cpu')}`}>
              <div className="metric-header">
                <div className="metric-title">
                  <span className="status-icon">
                    {getStatusIcon(getStatusColor(currentMetrics.cpu_percent, 'cpu'))}
                  </span>
                  <span>CPU Usage</span>
                </div>
                <div className="metric-value">
                  {currentMetrics.cpu_percent.toFixed(1)}%
                </div>
              </div>
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${currentMetrics.cpu_percent}%` }}
                ></div>
              </div>
              <div className="metric-footer">
                <span>Load Average:</span>
                <code>
                  {currentMetrics.load_average.map(l => l.toFixed(2)).join(' · ')}
                </code>
              </div>
            </div>

            {/* Memory */}
            <div className={`metric-card status-${getStatusColor(currentMetrics.memory_percent, 'memory')}`}>
              <div className="metric-header">
                <div className="metric-title">
                  <span className="status-icon">
                    {getStatusIcon(getStatusColor(currentMetrics.memory_percent, 'memory'))}
                  </span>
                  <span>Memory Usage</span>
                </div>
                <div className="metric-value">
                  {currentMetrics.memory_percent.toFixed(1)}%
                </div>
              </div>
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${currentMetrics.memory_percent}%` }}
                ></div>
              </div>
              <div className="metric-footer">
                <span>Used:</span>
                <code>
                  {((systemInfo.total_memory_gb * currentMetrics.memory_percent) / 100).toFixed(1)} GB / {systemInfo.total_memory_gb} GB
                </code>
              </div>
            </div>

            {/* Disk */}
            <div className={`metric-card status-${getStatusColor(currentMetrics.disk_percent, 'disk')}`}>
              <div className="metric-header">
                <div className="metric-title">
                  <span className="status-icon">
                    {getStatusIcon(getStatusColor(currentMetrics.disk_percent, 'disk'))}
                  </span>
                  <span>Disk Usage</span>
                </div>
                <div className="metric-value">
                  {currentMetrics.disk_percent.toFixed(1)}%
                </div>
              </div>
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${currentMetrics.disk_percent}%` }}
                ></div>
              </div>
              <div className="metric-footer">
                <span>Used:</span>
                <code>
                  {((systemInfo.total_disk_gb * currentMetrics.disk_percent) / 100).toFixed(0)} GB / {systemInfo.total_disk_gb} GB
                </code>
              </div>
            </div>
          </div>

          {/* Charts */}
          <div className="charts-section">
            {/* CPU Chart */}
            <div className="chart-container">
              <div className="chart-header">
                <h2>CPU Usage (Ultima Ora)</h2>
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={metrics}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                  <XAxis 
                    dataKey="timestamp" 
                    stroke="var(--text-tertiary)"
                    style={{ fontSize: '12px' }}
                  />
                  <YAxis 
                    stroke="var(--text-tertiary)"
                    style={{ fontSize: '12px' }}
                    domain={[0, 100]}
                    ticks={[0, 25, 50, 75, 100]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-primary)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                    }}
                    formatter={(value: number) => `${value.toFixed(1)}%`}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="cpu_percent" 
                    stroke="var(--accent-primary)" 
                    strokeWidth={2}
                    dot={false}
                    name="CPU %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Memory Chart */}
            <div className="chart-container">
              <div className="chart-header">
                <h2>Memory Usage (Ultima Ora)</h2>
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={metrics}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                  <XAxis 
                    dataKey="timestamp" 
                    stroke="var(--text-tertiary)"
                    style={{ fontSize: '12px' }}
                  />
                  <YAxis 
                    stroke="var(--text-tertiary)"
                    style={{ fontSize: '12px' }}
                    domain={[0, 100]}
                    ticks={[0, 25, 50, 75, 100]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-primary)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                    }}
                    formatter={(value: number) => `${value.toFixed(1)}%`}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="memory_percent" 
                    stroke="var(--accent-secondary)" 
                    strokeWidth={2}
                    dot={false}
                    name="Memory %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};

export default MonitoringPerformance;
