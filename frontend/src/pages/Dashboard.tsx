/**
 * Dashboard Page - Main overview page
 */
import React, { useEffect, useState } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import apiService from '../services/api';
import type { ThreatStats, Target } from '../types';
import './Dashboard.css';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<ThreatStats | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh ogni 30s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [threatsData, targetsData] = await Promise.all([
        apiService.getThreatStats(),
        apiService.getTargets()
      ]);
      setStats(threatsData);
      setTargets(targetsData.results);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  const COLORS = ['#ff4757', '#ffa502', '#ffd32d', '#26de81'];

  const severityData = [
    { name: 'Critical', value: stats?.critical_threats || 0, color: '#ff4757' },
    { name: 'High', value: stats?.high_threats || 0, color: '#ffa502' },
    { name: 'Medium', value: stats?.medium_threats || 0, color: '#ffd32d' },
    { name: 'Low', value: stats?.low_threats || 0, color: '#26de81' },
  ];

  const targetStatusData = [
    { name: 'Online', value: targets.filter(t => t.status === 'online').length },
    { name: 'Offline', value: targets.filter(t => t.status === 'offline').length },
    { name: 'Error', value: targets.filter(t => t.status === 'error').length },
    { name: 'Pending', value: targets.filter(t => t.status === 'pending').length },
  ];

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <button onClick={loadData} className="btn-refresh">Refresh</button>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">⚠️</div>
          <div className="stat-content">
            <div className="stat-value">{stats?.total_threats || 0}</div>
            <div className="stat-label">Total Threats</div>
          </div>
        </div>

        <div className="stat-card critical">
          <div className="stat-icon">🚨</div>
          <div className="stat-content">
            <div className="stat-value">{stats?.critical_threats || 0}</div>
            <div className="stat-label">Critical</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🛡️</div>
          <div className="stat-content">
            <div className="stat-value">{stats?.blocked_ips || 0}</div>
            <div className="stat-label">Blocked IPs</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🎯</div>
          <div className="stat-content">
            <div className="stat-value">{targets.length}</div>
            <div className="stat-label">Targets</div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="charts-grid">
        <div className="chart-card">
          <h3>Threats by Severity</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={severityData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                {severityData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Target Status</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={targetStatusData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#667eea" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Attackers */}
      <div className="table-card">
        <h3>Top Attackers</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>IP Address</th>
              <th>Attack Count</th>
            </tr>
          </thead>
          <tbody>
            {stats?.top_attackers.slice(0, 10).map((attacker, idx) => (
              <tr key={idx}>
                <td>{attacker.source_ip}</td>
                <td><span className="badge">{attacker.count}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
