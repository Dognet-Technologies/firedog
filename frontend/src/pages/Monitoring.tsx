/**
 * Monitoring Page — tabbed: Traffic | Performance
 * Migrated from MonitoringTraffic.tsx and MonitoringPerformance.tsx
 */
import React, { useState, useMemo } from 'react';
import { AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import PageHeader from '../components/shared/PageHeader';
import TabBar from '../components/shared/TabBar';
import './Monitoring.css';

type TabId = 'traffic' | 'performance';

const TABS = [
  { id: 'traffic' as TabId, label: 'Traffic' },
  { id: 'performance' as TabId, label: 'Performance' },
];

type TimeRange = '24h' | '7d' | '30d';

// TODO: replace with real API call when traffic/performance endpoint is available
const generateTrafficData = (range: TimeRange): Array<{ time: string; inbound: number; outbound: number; dropped: number }> => {
  const points = range === '24h' ? 24 : range === '7d' ? 7 : 30;
  const label = range === '24h' ? 'h' : range === '7d' ? 'd' : 'd';
  return Array.from({ length: points }, (_, i) => ({
    time: `${points - i}${label}`,
    inbound: Math.floor(Math.random() * 900 + 200),
    outbound: Math.floor(Math.random() * 500 + 100),
    dropped: Math.floor(Math.random() * 60),
  }));
};

const generateProtocolData = (): Array<{ name: string; packets: number; pct: number }> => [
  { name: 'TCP', packets: 68450, pct: 65 },
  { name: 'UDP', packets: 26200, pct: 25 },
  { name: 'ICMP', packets: 8360, pct: 8 },
  { name: 'Other', packets: 2090, pct: 2 },
];

const generateTopIPs = (): Array<{ ip: string; packets: number; bytes: string; direction: string }> => [
  { ip: '45.33.32.156', packets: 12400, bytes: '2.1 GB', direction: 'inbound' },
  { ip: '198.51.100.23', packets: 8900, bytes: '1.4 GB', direction: 'inbound' },
  { ip: '203.0.113.45', packets: 6700, bytes: '980 MB', direction: 'inbound' },
  { ip: '192.168.1.1', packets: 5400, bytes: '720 MB', direction: 'outbound' },
  { ip: '10.0.0.254', packets: 3200, bytes: '480 MB', direction: 'outbound' },
];

const generateCPUData = (range: TimeRange): Array<{ time: string; cpu: number; load1: number }> => {
  const points = range === '24h' ? 24 : range === '7d' ? 7 : 30;
  const label = range === '24h' ? 'h' : 'd';
  return Array.from({ length: points }, (_, i) => ({
    time: `${points - i}${label}`,
    cpu: Math.min(100, Math.floor(Math.random() * 60 + 10)),
    load1: parseFloat((Math.random() * 4 + 0.5).toFixed(2)),
  }));
};

const generateMemoryData = (range: TimeRange): Array<{ time: string; used: number; total: number }> => {
  const points = range === '24h' ? 24 : range === '7d' ? 7 : 30;
  const label = range === '24h' ? 'h' : 'd';
  return Array.from({ length: points }, (_, i) => ({
    time: `${points - i}${label}`,
    used: Math.floor(Math.random() * 4096 + 2048),
    total: 8192,
  }));
};

const generateConnectionData = (range: TimeRange): Array<{ time: string; active: number; new_conn: number }> => {
  const points = range === '24h' ? 24 : range === '7d' ? 7 : 30;
  const label = range === '24h' ? 'h' : 'd';
  return Array.from({ length: points }, (_, i) => ({
    time: `${points - i}${label}`,
    active: Math.floor(Math.random() * 800 + 200),
    new_conn: Math.floor(Math.random() * 200 + 50),
  }));
};

const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-primary)',
    borderRadius: '8px',
    fontSize: '12px',
  },
};

// ============================================================
// Traffic Tab
// ============================================================

const TrafficTab: React.FC = () => {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');

  const trafficData = useMemo(() => generateTrafficData(timeRange), [timeRange]);
  const protocolData = useMemo(() => generateProtocolData(), []);
  const topIPs = useMemo(() => generateTopIPs(), []);

  const totalIn = trafficData.reduce((s, d) => s + d.inbound, 0);
  const totalOut = trafficData.reduce((s, d) => s + d.outbound, 0);
  const totalDropped = trafficData.reduce((s, d) => s + d.dropped, 0);

  return (
    <div className="mon-tab-content">
      {/* TODO: replace with real API call */}
      <div className="mon-filter-row">
        <span className="mon-note">Mock data — TODO: replace with real API call</span>
        <select
          className="mon-select"
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value as TimeRange)}
        >
          <option value="24h">Last 24h</option>
          <option value="7d">Last 7d</option>
          <option value="30d">Last 30d</option>
        </select>
      </div>

      <div className="mon-stat-cards">
        <div className="mon-stat-card">
          <div className="mon-stat-label">Total Inbound</div>
          <div className="mon-stat-value">{totalIn.toLocaleString()}</div>
          <div className="mon-stat-unit">packets</div>
        </div>
        <div className="mon-stat-card">
          <div className="mon-stat-label">Total Outbound</div>
          <div className="mon-stat-value">{totalOut.toLocaleString()}</div>
          <div className="mon-stat-unit">packets</div>
        </div>
        <div className="mon-stat-card mon-stat-danger">
          <div className="mon-stat-label">Dropped</div>
          <div className="mon-stat-value">{totalDropped.toLocaleString()}</div>
          <div className="mon-stat-unit">packets</div>
        </div>
      </div>

      <div className="mon-chart-card">
        <h3 className="mon-card-title">Inbound / Outbound Traffic</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={trafficData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="monIn" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="monOut" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--status-success)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--status-success)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
            <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
            <Tooltip {...CHART_TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--text-secondary)' }} />
            <Area type="monotone" dataKey="inbound" stroke="var(--accent-primary)" fill="url(#monIn)" name="Inbound" />
            <Area type="monotone" dataKey="outbound" stroke="var(--status-success)" fill="url(#monOut)" name="Outbound" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mon-grid-2">
        <div className="mon-chart-card">
          <h3 className="mon-card-title">Protocol Distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={protocolData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="pct" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} name="%" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mon-card">
          <h3 className="mon-card-title">Top IP Addresses by Volume</h3>
          <div className="mon-table-wrapper">
            <table className="mon-table">
              <thead>
                <tr>
                  <th>IP</th>
                  <th>Packets</th>
                  <th>Volume</th>
                  <th>Dir.</th>
                </tr>
              </thead>
              <tbody>
                {topIPs.map((ip) => (
                  <tr key={ip.ip}>
                    <td className="mon-mono">{ip.ip}</td>
                    <td>{ip.packets.toLocaleString()}</td>
                    <td>{ip.bytes}</td>
                    <td>
                      <span className={`mon-dir-badge ${ip.direction}`}>{ip.direction}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// Performance Tab
// ============================================================

const PerformanceTab: React.FC = () => {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');

  const cpuData = useMemo(() => generateCPUData(timeRange), [timeRange]);
  const memData = useMemo(() => generateMemoryData(timeRange), [timeRange]);
  const connData = useMemo(() => generateConnectionData(timeRange), [timeRange]);

  const avgCPU = Math.round(cpuData.reduce((s, d) => s + d.cpu, 0) / cpuData.length);
  const lastMem = memData[memData.length - 1];
  const memPct = lastMem ? Math.round((lastMem.used / lastMem.total) * 100) : 0;
  const lastConn = connData[connData.length - 1]?.active ?? 0;

  return (
    <div className="mon-tab-content">
      {/* TODO: replace with real API call */}
      <div className="mon-filter-row">
        <span className="mon-note">Mock data — TODO: replace with real API call</span>
        <select
          className="mon-select"
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value as TimeRange)}
        >
          <option value="24h">Last 24h</option>
          <option value="7d">Last 7d</option>
          <option value="30d">Last 30d</option>
        </select>
      </div>

      <div className="mon-stat-cards">
        <div className="mon-stat-card">
          <div className="mon-stat-label">Avg CPU</div>
          <div className="mon-stat-value">{avgCPU}%</div>
        </div>
        <div className="mon-stat-card">
          <div className="mon-stat-label">Memory Used</div>
          <div className="mon-stat-value">{memPct}%</div>
          <div className="mon-stat-unit">{lastMem ? `${(lastMem.used / 1024).toFixed(1)} / ${(lastMem.total / 1024).toFixed(1)} GB` : '—'}</div>
        </div>
        <div className="mon-stat-card">
          <div className="mon-stat-label">Active Connections</div>
          <div className="mon-stat-value">{lastConn.toLocaleString()}</div>
        </div>
      </div>

      <div className="mon-chart-card">
        <h3 className="mon-card-title">CPU Usage %</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={cpuData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
            <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
            <Tooltip {...CHART_TOOLTIP_STYLE} />
            <Line type="monotone" dataKey="cpu" stroke="var(--status-warning)" dot={false} name="CPU %" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mon-grid-2">
        <div className="mon-chart-card">
          <h3 className="mon-card-title">Memory Usage (MB)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={memData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="monMem" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--status-info)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--status-info)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="used" stroke="var(--status-info)" fill="url(#monMem)" name="Used MB" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="mon-chart-card">
          <h3 className="mon-card-title">Active Connections</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={connData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="active" stroke="var(--status-success)" dot={false} name="Active" strokeWidth={2} />
              <Line type="monotone" dataKey="new_conn" stroke="var(--accent-primary)" dot={false} name="New" strokeWidth={1} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// Main Monitoring Component
// ============================================================

const Monitoring: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('traffic');

  return (
    <div className="monitoring-page">
      <PageHeader
        title="Monitoring"
        subtitle="Network traffic and system performance"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        }
      />

      <div className="mon-tabs">
        <TabBar tabs={TABS} activeTab={activeTab} onChange={(id) => setActiveTab(id as TabId)} />
      </div>

      {activeTab === 'traffic' && <TrafficTab />}
      {activeTab === 'performance' && <PerformanceTab />}
    </div>
  );
};

export default Monitoring;
