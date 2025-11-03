/**
 * Dashboard Page - Chronograf Style with Resizable Widgets
 */
import React, { useEffect, useState } from 'react';
import { Responsive, WidthProvider, Layout } from 'react-grid-layout';
import { LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import apiService from '../services/api';
import type { ThreatStats, Target } from '../types';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './Dashboard.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

interface Widget {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  type: 'hosts' | 'threats' | 'traffic' | 'top-ips' | 'line-chart' | 'bar-chart';
  title: string;
}

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<ThreatStats | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [widgets, setWidgets] = useState<Widget[]>([
    { i: 'hosts', x: 0, y: 0, w: 6, h: 2, type: 'hosts', title: 'Host Alive' },
    { i: 'threats', x: 6, y: 0, w: 6, h: 2, type: 'threats', title: 'Top Threats' },
    { i: 'traffic', x: 0, y: 2, w: 6, h: 3, type: 'traffic', title: 'Network Traffic' },
    { i: 'top-ips', x: 6, y: 2, w: 6, h: 3, type: 'top-ips', title: 'Top IP Addresses' },
  ]);

  // Mock data for demo
  const trafficData = [
    { time: '00:00', upload: 4000, download: 2400 },
    { time: '04:00', upload: 3000, download: 1398 },
    { time: '08:00', upload: 2000, download: 9800 },
    { time: '12:00', upload: 2780, download: 3908 },
    { time: '16:00', upload: 1890, download: 4800 },
    { time: '20:00', upload: 2390, download: 3800 },
    { time: '23:59', upload: 3490, download: 4300 },
  ];

  const topThreatsData = [
    { name: 'SSH Bruteforce', count: 145, severity: 'critical' },
    { name: 'Port Scan', count: 98, severity: 'high' },
    { name: 'DDoS Attempt', count: 67, severity: 'critical' },
    { name: 'SQL Injection', count: 45, severity: 'high' },
    { name: 'XSS Attack', count: 23, severity: 'medium' },
  ];

  const topIPsData = [
    { ip: '192.168.1.105', traffic: 8500, status: 'high' },
    { ip: '10.0.0.45', traffic: 6200, status: 'medium' },
    { ip: '172.16.0.89', traffic: 5100, status: 'medium' },
    { ip: '192.168.1.203', traffic: 3800, status: 'low' },
    { ip: '10.0.0.167', traffic: 2400, status: 'low' },
  ];

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
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

  const handleLayoutChange = (layout: Layout[]) => {
    const updatedWidgets = widgets.map(widget => {
      const layoutItem = layout.find(l => l.i === widget.i);
      if (layoutItem) {
        return { ...widget, x: layoutItem.x, y: layoutItem.y, w: layoutItem.w, h: layoutItem.h };
      }
      return widget;
    });
    setWidgets(updatedWidgets);
  };

  const addWidget = (type: Widget['type']) => {
    const newWidget: Widget = {
      i: `widget-${Date.now()}`,
      x: 0,
      y: Infinity, // Adds to bottom
      w: 6,
      h: 3,
      type,
      title: getWidgetTitle(type),
    };
    setWidgets([...widgets, newWidget]);
    setShowAddWidget(false);
  };

  const removeWidget = (widgetId: string) => {
    setWidgets(widgets.filter(w => w.i !== widgetId));
  };

  const getWidgetTitle = (type: Widget['type']): string => {
    const titles = {
      hosts: 'Host Alive',
      threats: 'Top Threats',
      traffic: 'Network Traffic',
      'top-ips': 'Top IP Addresses',
      'line-chart': 'Line Chart',
      'bar-chart': 'Bar Chart',
    };
    return titles[type];
  };

  const renderWidget = (widget: Widget) => {
    switch (widget.type) {
      case 'hosts':
        return (
          <div className="widget-content">
            <div className="hosts-list">
              {targets.slice(0, 5).map((target, idx) => (
                <div key={idx} className="host-item">
                  <div className="host-info">
                    <span className={`status-dot ${target.status === 'online' ? 'online' : 'offline'}`}></span>
                    <span className="host-name">{target.hostname}</span>
                    <span className="host-ip">{target.ip_address}</span>
                  </div>
                  <span className={`host-status ${target.status}`}>{target.status}</span>
                </div>
              ))}
              {targets.length === 0 && (
                <div className="empty-widget">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <p>No hosts configured</p>
                </div>
              )}
            </div>
          </div>
        );

      case 'threats':
        return (
          <div className="widget-content">
            <div className="threats-list">
              {topThreatsData.map((threat, idx) => (
                <div key={idx} className="threat-item">
                  <div className="threat-info">
                    <span className={`severity-badge ${threat.severity}`}>{threat.severity}</span>
                    <span className="threat-name">{threat.name}</span>
                  </div>
                  <span className="threat-count">{threat.count}</span>
                </div>
              ))}
            </div>
          </div>
        );

      case 'traffic':
        return (
          <div className="widget-content">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trafficData}>
                <defs>
                  <linearGradient id="uploadGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00c9ff" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00c9ff" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="downloadGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#32d74b" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#32d74b" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3139" />
                <XAxis dataKey="time" stroke="#8e91a0" />
                <YAxis stroke="#8e91a0" />
                <Tooltip 
                  contentStyle={{ 
                    background: '#1f2228', 
                    border: '1px solid #2d3139',
                    borderRadius: '8px',
                    color: '#fff'
                  }} 
                />
                <Area type="monotone" dataKey="upload" stroke="#00c9ff" fillOpacity={1} fill="url(#uploadGradient)" />
                <Area type="monotone" dataKey="download" stroke="#32d74b" fillOpacity={1} fill="url(#downloadGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        );

      case 'top-ips':
        return (
          <div className="widget-content">
            <div className="ips-list">
              {topIPsData.map((item, idx) => (
                <div key={idx} className="ip-item">
                  <div className="ip-info">
                    <span className="ip-rank">#{idx + 1}</span>
                    <span className="ip-address">{item.ip}</span>
                  </div>
                  <div className="ip-traffic">
                    <div className="traffic-bar">
                      <div 
                        className={`traffic-fill ${item.status}`} 
                        style={{ width: `${(item.traffic / 10000) * 100}%` }}
                      ></div>
                    </div>
                    <span className="traffic-value">{(item.traffic / 1000).toFixed(1)} GB</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      default:
        return (
          <div className="widget-content">
            <div className="empty-widget">
              <p>Widget type: {widget.type}</p>
            </div>
          </div>
        );
    }
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="dashboard-chronograf">
      {/* Dashboard Header */}
      <div className="dashboard-header">
        <div className="header-left">
          <h1>Dashboard</h1>
          <button className="btn-icon" onClick={loadData} title="Refresh">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
          </button>
        </div>
        <div className="header-right">
          <button className="btn-add-cell" onClick={() => setShowAddWidget(!showAddWidget)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Cell
          </button>
        </div>
      </div>

      {/* Add Widget Menu */}
      {showAddWidget && (
        <div className="add-widget-menu">
          <div className="menu-header">
            <h3>Add Cell</h3>
            <button className="btn-close" onClick={() => setShowAddWidget(false)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
          <div className="widget-types">
            <button className="widget-type-btn" onClick={() => addWidget('hosts')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
              </svg>
              Host Status
            </button>
            <button className="widget-type-btn" onClick={() => addWidget('threats')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              Threats
            </button>
            <button className="widget-type-btn" onClick={() => addWidget('traffic')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              Traffic
            </button>
            <button className="widget-type-btn" onClick={() => addWidget('top-ips')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="8" y1="6" x2="21" y2="6" />
                <line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" />
                <line x1="3" y1="12" x2="3.01" y2="12" />
                <line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
              Top IPs
            </button>
          </div>
        </div>
      )}

      {/* Widgets Grid */}
      <ResponsiveGridLayout
        className="dashboard-grid"
        layouts={{ lg: widgets }}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={80}
        onLayoutChange={handleLayoutChange}
        isDraggable={true}
        isResizable={true}
        compactType="vertical"
        preventCollision={false}
      >
        {widgets.map((widget) => (
          <div key={widget.i} className="widget-card">
            <div className="widget-header">
              <h3 className="widget-title">{widget.title}</h3>
              <div className="widget-actions">
                <button 
                  className="btn-icon-sm" 
                  onClick={() => removeWidget(widget.i)}
                  title="Remove"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            </div>
            {renderWidget(widget)}
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
};

export default Dashboard;
