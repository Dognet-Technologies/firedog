/**
 * Dashboard Page — refactored with react-grid-layout, widget builder modal,
 * time range + auto-refresh selectors, edit mode
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Link } from 'react-router-dom';
import apiService from '../services/api';
import type { ThreatStats, Target, Dashboard as DashboardType, Widget as ApiWidget } from '../types';
import StatusDot from '../components/shared/StatusDot';
import DataTooltip from '../components/shared/DataTooltip';
import SeverityBadge from '../components/shared/SeverityBadge';
import CountryFlag from '../components/shared/CountryFlag';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './Dashboard.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

type TimeRange = '24h' | '7d' | '30d';
type AutoRefresh = 'off' | '30s' | '1m' | '5m';

interface GridWidget {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  type: ApiWidget['widget_type'];
  title: string;
  apiId?: number;
}

interface WidgetBuilderStep {
  step: 1 | 2 | 3;
  selectedType?: ApiWidget['widget_type'];
  title: string;
  timeRange: TimeRange;
}

const WIDGET_TYPE_LABELS: Record<ApiWidget['widget_type'], string> = {
  threat_summary: 'Threat Summary',
  threat_chart: 'Threat Chart',
  target_status: 'Target Status',
  recent_threats: 'Recent Threats',
  top_attackers: 'Top Attackers',
  rule_count: 'Rule Count',
  traffic_stats: 'Traffic Stats',
  activity_timeline: 'Activity Timeline',
  geo_map: 'Geo Map',
  custom: 'Custom',
};

const DEFAULT_WIDGETS: GridWidget[] = [
  { i: 'threat_summary', x: 0, y: 0, w: 3, h: 2, type: 'threat_summary', title: 'Threat Summary' },
  { i: 'target_status', x: 3, y: 0, w: 5, h: 2, type: 'target_status', title: 'Target Status' },
  { i: 'traffic_stats', x: 8, y: 0, w: 4, h: 2, type: 'traffic_stats', title: 'Traffic Stats' },
  { i: 'recent_threats', x: 0, y: 2, w: 6, h: 3, type: 'recent_threats', title: 'Recent Threats' },
  { i: 'top_attackers', x: 6, y: 2, w: 6, h: 3, type: 'top_attackers', title: 'Top Attackers' },
  { i: 'activity_timeline', x: 0, y: 5, w: 6, h: 3, type: 'activity_timeline', title: 'Activity Timeline' },
  { i: 'geo_map', x: 6, y: 5, w: 6, h: 3, type: 'geo_map', title: 'Geo Map' },
];

// Traffic fleet-wide arriva da apiService.getDashboardFleetTraffic dentro al
// componente. Niente più mock random: se l'endpoint non risponde restiamo
// con array vuoto (il widget mostra grafico vuoto).

// ============================================================
// Widget sub-components
// ============================================================

const ThreatSummaryWidget: React.FC<{ stats: ThreatStats | null }> = ({ stats }) => (
  <div className="widget-threat-summary">
    <DataTooltip
      title="Total Threats"
      type="count"
      description="Numero totale di eventi di sicurezza rilevati su tutta la flotta. Comprende minacce attive e risolte di tutti i livelli di severità."
      source="ThreatLog · /api/threats/stats/"
    >
      <div className="wts-number">{stats?.total_threats ?? '—'}</div>
    </DataTooltip>
    <div className="wts-label">Total Threats</div>
    <div className="wts-breakdown">
      <DataTooltip inline title="Critical Threats" type="count" description="Minacce con severity='critical': attacchi ad alto rischio che richiedono intervento immediato." source="ThreatLog">
        <span className="wts-crit">C: {stats?.critical_threats ?? 0}</span>
      </DataTooltip>
      <DataTooltip inline title="High Threats" type="count" description="Minacce con severity='high': eventi significativi che andrebbero analizzati entro breve." source="ThreatLog">
        <span className="wts-high">H: {stats?.high_threats ?? 0}</span>
      </DataTooltip>
      <DataTooltip inline title="Medium Threats" type="count" description="Minacce con severity='medium': anomalie rilevate che meritano monitoraggio ma non blocco immediato." source="ThreatLog">
        <span className="wts-med">M: {stats?.medium_threats ?? 0}</span>
      </DataTooltip>
    </div>
  </div>
);

const TrafficStatsWidget: React.FC<{ data: Array<{ time: string; in: number; out: number }> }> = ({ data }) => (
  <DataTooltip
    title="Network Traffic (24h)"
    type="delta"
    description="Traffico di rete inbound/outbound nelle ultime 24 ore. Ogni punto del grafico rappresenta la variazione (delta) dei pacchetti rispetto al campione precedente di FirewallStats, campionato ogni ora."
    source="FirewallStats API (dati approssimativi)"
  >
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
      <defs>
        <linearGradient id="tIn" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
          <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
        </linearGradient>
        <linearGradient id="tOut" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="var(--status-success)" stopOpacity={0.3} />
          <stop offset="95%" stopColor="var(--status-success)" stopOpacity={0} />
        </linearGradient>
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
      <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 9 }} interval={4} />
      <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 9 }} />
      <Tooltip
        contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: '8px', fontSize: '12px' }}
      />
      <Area type="monotone" dataKey="in" stroke="var(--accent-primary)" fill="url(#tIn)" name="Inbound" />
      <Area type="monotone" dataKey="out" stroke="var(--status-success)" fill="url(#tOut)" name="Outbound" />
    </AreaChart>
  </ResponsiveContainer>
  </DataTooltip>
);

const TargetStatusWidget: React.FC<{ targets: Target[] }> = ({ targets }) => (
  <div className="widget-target-status">
    {targets.length === 0 ? (
      <div className="widget-empty">No targets configured</div>
    ) : (
      <div className="wts-grid">
        {targets.slice(0, 12).map((t) => (
          <Link key={t.id} to={`/targets/${t.id}`} className="wts-target-mini">
            <StatusDot status={t.status as 'online' | 'offline' | 'error' | 'installing' | 'pending'} />
            <span className="wts-target-name">{t.hostname || t.ip_address}</span>
          </Link>
        ))}
        {targets.length > 12 && (
          <Link to="/targets" className="wts-target-more">+{targets.length - 12} more</Link>
        )}
      </div>
    )}
  </div>
);

const RecentThreatsWidget: React.FC<{ stats: ThreatStats | null }> = ({ stats }) => {
  const threats = stats?.recent_threats ?? [];
  if (threats.length === 0) {
    return <div className="widget-empty">No recent threats</div>;
  }
  return (
    <div className="widget-recent-threats">
      {threats.slice(0, 8).map((t) => (
        <div key={t.id} className="wrt-item">
          <SeverityBadge severity={t.severity} />
          <span className="wrt-ip">{t.source_ip}</span>
          <span className="wrt-proto">{t.protocol}</span>
          <span className="wrt-time">{new Date(t.detected_at).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      ))}
    </div>
  );
};

const TopAttackersWidget: React.FC<{ stats: ThreatStats | null }> = ({ stats }) => {
  const attackers = stats?.top_attackers ?? [];
  if (attackers.length === 0) {
    return <div className="widget-empty">No attacker data</div>;
  }
  return (
    <div className="widget-top-attackers">
      <div className="wta-header">
        <span>IP</span>
        <span>Hits</span>
      </div>
      {attackers.slice(0, 8).map((a, idx) => (
        <div key={idx} className="wta-item">
          <span className="wta-ip">{a.source_ip}</span>
          <DataTooltip inline title="Attacchi da questo IP" type="count"
            description="Numero di eventi di minaccia registrati per questo indirizzo IP sorgente nel periodo selezionato. Un singolo IP può generare più eventi in sessioni distinte."
            source="ThreatLog.source_ip">
            <span className="wta-count">{a.count}</span>
          </DataTooltip>
        </div>
      ))}
    </div>
  );
};

const ActivityTimelineWidget: React.FC<{ stats: ThreatStats | null }> = ({ stats }) => {
  const threats = stats?.recent_threats ?? [];
  if (threats.length === 0) {
    return <div className="widget-empty">No activity</div>;
  }
  return (
    <div className="widget-timeline">
      {threats.slice(0, 6).map((t) => (
        <div key={t.id} className="wat-item">
          <div className="wat-dot" />
          <div className="wat-content">
            <span className="wat-msg">Threat from {t.source_ip}</span>
            <span className="wat-time">{new Date(t.detected_at).toLocaleString('it-IT')}</span>
          </div>
          <SeverityBadge severity={t.severity} />
        </div>
      ))}
    </div>
  );
};

const GeoMapWidget: React.FC<{ stats: ThreatStats | null }> = ({ stats: _stats }) => {
  // Sorgente: /api/dashboard/geo/ — aggregato dei NetworkFlow per country_code
  // (peer remoti pubblici visti dai target, lookup via geoip2 lato server).
  // Funziona indipendentemente dai ThreatLog: mostra traffico legittimo
  // outbound + qualunque connessione attiva verso IP pubblici.
  const [geoData, setGeoData] = useState<Array<{ country: string; count: number; pct: number; name: string }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiService.getDashboardGeo()
      .then(resp => {
        if (cancelled) return;
        setGeoData(resp.countries.slice(0, 6).map(c => ({
          country: c.country_code, name: c.country_name, count: c.times_seen, pct: c.pct,
        })));
      })
      .catch(() => { if (!cancelled) setGeoData([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    // refresh allineato al polling default della Dashboard (loadData ogni 30s+);
    // un re-fetch ogni 60s qui evita di legare il widget allo state del parent.
    const id = setInterval(() => {
      apiService.getDashboardGeo()
        .then(resp => setGeoData(resp.countries.slice(0, 6).map(c => ({
          country: c.country_code, name: c.country_name, count: c.times_seen, pct: c.pct,
        }))))
        .catch(() => {});
    }, 60_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading) return <div className="widget-empty">Loading…</div>;
  if (geoData.length === 0) {
    return (
      <div className="widget-empty">
        Nessun dato geografico ancora — i peer remoti vengono raccolti dai target via cron (5min) e geo-localizzati lato server.
      </div>
    );
  }

  return (
    <div className="widget-geo">
      {geoData.map((g) => (
        <div key={g.country} className="wg-item">
          <CountryFlag countryCode={g.country} showName />
          <DataTooltip inline title={`Attacchi da ${g.country}`} type="count"
            description={`Numero stimato di minacce provenienti da questo paese (${g.pct}% del totale), basato sulla geolocalizzazione degli IP sorgente rilevati nei log. Dato approssimativo.`}
            source="GeoIP lookup · ThreatLog.source_ip (dati demo)">
            <div className="wg-bar-wrap">
              <div className="wg-bar" style={{ width: `${g.pct}%` }} />
            </div>
          </DataTooltip>
          <DataTooltip inline title={`Conteggio assoluto · ${g.country}`} type="count"
            description="Numero assoluto di eventi minaccia attribuiti a questo paese nel periodo selezionato."
            source="ThreatLog (dati demo)">
            <span className="wg-count">{g.count}</span>
          </DataTooltip>
        </div>
      ))}
    </div>
  );
};

// ============================================================
// Main Dashboard Component
// ============================================================

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<ThreatStats | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [dashboards, setDashboards] = useState<DashboardType[]>([]);
  const [selectedDashboardId, setSelectedDashboardId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  // Le preferenze "time range" e "auto refresh" sono persistite in localStorage
  // così sopravvivono a reload/navigazione/logout. Lazy initializer per leggere
  // una sola volta al mount; setter custom per scriverle al cambio.
  const [timeRange, setTimeRangeState] = useState<TimeRange>(() => {
    const v = typeof window !== 'undefined' ? window.localStorage.getItem('fd.dashboard.timeRange') : null;
    return (v === '24h' || v === '7d' || v === '30d') ? v : '24h';
  });
  const setTimeRange = (v: TimeRange) => {
    setTimeRangeState(v);
    try { window.localStorage.setItem('fd.dashboard.timeRange', v); } catch { /* private mode */ }
  };

  const [autoRefresh, setAutoRefreshState] = useState<AutoRefresh>(() => {
    const v = typeof window !== 'undefined' ? window.localStorage.getItem('fd.dashboard.autoRefresh') : null;
    return (v === 'off' || v === '30s' || v === '1m' || v === '5m') ? v : 'off';
  });
  const setAutoRefresh = (v: AutoRefresh) => {
    setAutoRefreshState(v);
    try { window.localStorage.setItem('fd.dashboard.autoRefresh', v); } catch { /* private mode */ }
  };
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [widgets, setWidgets] = useState<GridWidget[]>(DEFAULT_WIDGETS);
  // trafficData: alimentato da /api/dashboard/fleet-traffic/ (aggregato
  // fleet-wide dei delta input/output_packets per ora). Vedi loadData().
  const [trafficData, setTrafficData] = useState<Array<{ time: string; in: number; out: number }>>([]);

  // Widget builder state
  const [builderState, setBuilderState] = useState<WidgetBuilderStep>({
    step: 1,
    title: '',
    timeRange: '24h',
  });

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [statsData, targetsData, trafficResp] = await Promise.all([
        apiService.getThreatStats(),
        apiService.getTargets(),
        apiService.getDashboardFleetTraffic(24).catch(() => ({ series: [] as Array<{ time: string; in: number; out: number }> })),
      ]);
      setStats(statsData);
      setTargets(targetsData.results);
      setTrafficData(trafficResp.series.map(s => ({ time: s.time, in: s.in, out: s.out })));
    } catch (err) {
      console.error('Dashboard loadData error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDashboards = useCallback(async () => {
    try {
      const resp = await apiService.getDashboards();
      setDashboards(resp.results);
      if (resp.results.length > 0 && !selectedDashboardId) {
        const defaultDb = resp.results.find((d) => d.is_default) || resp.results[0];
        setSelectedDashboardId(defaultDb.id);
        // Load widgets from dashboard if they have layout_config
        if (defaultDb.layout_config?.widgets) {
          setWidgets(defaultDb.layout_config.widgets);
        }
      }
    } catch (err) {
      console.error('Dashboard loadDashboards error:', err);
    }
  }, [selectedDashboardId]);

  useEffect(() => {
    loadData();
    loadDashboards();
  }, []);

  // Auto refresh
  useEffect(() => {
    if (autoRefresh === 'off') return;
    const ms = autoRefresh === '30s' ? 30000 : autoRefresh === '1m' ? 60000 : 300000;
    const timer = setInterval(loadData, ms);
    return () => clearInterval(timer);
  }, [autoRefresh, loadData]);

  const handleLayoutChange = (layout: Layout[]) => {
    const updated = widgets.map((w) => {
      const li = layout.find((l) => l.i === w.i);
      if (li) return { ...w, x: li.x, y: li.y, w: li.w, h: li.h };
      return w;
    });
    setWidgets(updated);

    // Debounced save to backend
    if (selectedDashboardId) {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(async () => {
        try {
          await apiService.updateDashboard(selectedDashboardId, {
            layout_config: { widgets: updated },
          });
        } catch (err) {
          console.error('Dashboard layout save error:', err);
        }
      }, 1000);
    }
  };

  const handleAddWidget = () => {
    if (!builderState.selectedType) return;
    const newWidget: GridWidget = {
      i: `${builderState.selectedType}-${Date.now()}`,
      x: 0,
      y: Infinity,
      w: 4,
      h: 3,
      type: builderState.selectedType,
      title: builderState.title || WIDGET_TYPE_LABELS[builderState.selectedType],
    };
    setWidgets([...widgets, newWidget]);
    setShowAddWidget(false);
    setBuilderState({ step: 1, title: '', timeRange: '24h' });
  };

  const handleRemoveWidget = (widgetId: string) => {
    setWidgets(widgets.filter((w) => w.i !== widgetId));
  };

  const renderWidgetContent = (widget: GridWidget) => {
    switch (widget.type) {
      case 'threat_summary':
        return <ThreatSummaryWidget stats={stats} />;
      case 'traffic_stats':
        return <TrafficStatsWidget data={trafficData} />;
      case 'target_status':
        return <TargetStatusWidget targets={targets} />;
      case 'recent_threats':
        return <RecentThreatsWidget stats={stats} />;
      case 'top_attackers':
        return <TopAttackersWidget stats={stats} />;
      case 'activity_timeline':
        return <ActivityTimelineWidget stats={stats} />;
      case 'geo_map':
        return <GeoMapWidget stats={stats} />;
      default:
        return <div className="widget-empty">Widget type: {widget.type}</div>;
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <p>Loading dashboard...</p>
      </div>
    );
  }

  const currentDashboard = dashboards.find((d) => d.id === selectedDashboardId);

  return (
    <div className="dashboard-page">
      {/* ===== HEADER BAR ===== */}
      <div className="db-header">
        <div className="db-header-left">
          {dashboards.length > 1 ? (
            <select
              className="db-select"
              value={selectedDashboardId ?? ''}
              onChange={(e) => setSelectedDashboardId(parseInt(e.target.value, 10))}
            >
              {dashboards.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          ) : (
            <h2 className="db-title">{currentDashboard?.name ?? 'Dashboard'}</h2>
          )}
        </div>

        <div className="db-header-right">
          <select
            className="db-select"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as TimeRange)}
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7d</option>
            <option value="30d">Last 30d</option>
          </select>

          <select
            className="db-select"
            value={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.value as AutoRefresh)}
          >
            <option value="off">Auto-refresh: Off</option>
            <option value="30s">Every 30s</option>
            <option value="1m">Every 1m</option>
            <option value="5m">Every 5m</option>
          </select>

          <button
            className={`db-btn${editMode ? ' db-btn-active' : ''}`}
            onClick={() => setEditMode(!editMode)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            {editMode ? 'Done' : 'Edit'}
          </button>

          {editMode && (
            <button className="db-btn db-btn-primary" onClick={() => setShowAddWidget(true)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Widget
            </button>
          )}
        </div>
      </div>

      {/* ===== STATS STRIP ===== */}
      {stats && (
        <div className="db-stats-strip">
          <div className="db-stat">
            <span className="db-stat-value">{stats.total_threats}</span>
            <span className="db-stat-label">Total Threats</span>
          </div>
          <div className="db-stat db-stat-danger">
            <span className="db-stat-value">{stats.critical_threats}</span>
            <span className="db-stat-label">Critical</span>
          </div>
          <div className="db-stat db-stat-warning">
            <span className="db-stat-value">{stats.high_threats}</span>
            <span className="db-stat-label">High</span>
          </div>
          <div className="db-stat db-stat-info">
            <span className="db-stat-value">{stats.medium_threats}</span>
            <span className="db-stat-label">Medium</span>
          </div>
          <div className="db-stat">
            <span className="db-stat-value">{stats.blocked_ips}</span>
            <span className="db-stat-label">Blocked IPs</span>
          </div>
          <div className="db-stat db-stat-success">
            <span className="db-stat-value">{targets.filter((t) => t.status === 'online').length}</span>
            <span className="db-stat-label">Online Targets</span>
          </div>
        </div>
      )}

      {/* ===== WIDGET GRID ===== */}
      <div className="db-grid-container">
        <ResponsiveGridLayout
          className="layout"
          breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
          cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
          rowHeight={80}
          isDraggable={editMode}
          isResizable={editMode}
          onLayoutChange={handleLayoutChange}
          layouts={{
            lg: widgets.map((w) => ({ i: w.i, x: w.x, y: w.y, w: w.w, h: w.h, minW: 2, minH: 2 })),
          }}
        >
          {widgets.map((widget) => (
            <div key={widget.i} className={`db-widget${editMode ? ' db-widget-edit' : ''}`}>
              <div className="db-widget-header">
                {editMode && (
                  <span className="db-widget-drag-handle" title="Drag to move">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="9" cy="5" r="1" /><circle cx="9" cy="12" r="1" /><circle cx="9" cy="19" r="1" />
                      <circle cx="15" cy="5" r="1" /><circle cx="15" cy="12" r="1" /><circle cx="15" cy="19" r="1" />
                    </svg>
                  </span>
                )}
                <span className="db-widget-title">{widget.title}</span>
                {editMode && (
                  <button
                    className="db-widget-remove"
                    onClick={() => handleRemoveWidget(widget.i)}
                    title="Remove widget"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                )}
              </div>
              <div className="db-widget-content">
                {renderWidgetContent(widget)}
              </div>
            </div>
          ))}
        </ResponsiveGridLayout>
      </div>

      {/* ===== WIDGET BUILDER MODAL ===== */}
      {showAddWidget && (
        <div className="modal-backdrop" onClick={() => setShowAddWidget(false)}>
          <div className="db-modal" onClick={(e) => e.stopPropagation()}>
            <div className="db-modal-header">
              <h3>Add Widget — Step {builderState.step} of 3</h3>
              <button className="db-modal-close" onClick={() => setShowAddWidget(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="db-modal-body">
              {builderState.step === 1 && (
                <div className="db-builder-step1">
                  <p className="db-builder-hint">Select a widget type:</p>
                  <div className="db-widget-type-grid">
                    {(Object.entries(WIDGET_TYPE_LABELS) as Array<[ApiWidget['widget_type'], string]>).map(([type, label]) => (
                      <button
                        key={type}
                        className={`db-widget-type-btn${builderState.selectedType === type ? ' selected' : ''}`}
                        onClick={() => setBuilderState({ ...builderState, selectedType: type })}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {builderState.step === 2 && (
                <div className="db-builder-step2">
                  <div className="db-form-group">
                    <label className="db-label">Widget Title</label>
                    <input
                      type="text"
                      className="db-input"
                      value={builderState.title}
                      onChange={(e) => setBuilderState({ ...builderState, title: e.target.value })}
                      placeholder={builderState.selectedType ? WIDGET_TYPE_LABELS[builderState.selectedType] : ''}
                    />
                  </div>
                  <div className="db-form-group">
                    <label className="db-label">Time Range</label>
                    <select
                      className="db-input"
                      value={builderState.timeRange}
                      onChange={(e) => setBuilderState({ ...builderState, timeRange: e.target.value as TimeRange })}
                    >
                      <option value="24h">Last 24h</option>
                      <option value="7d">Last 7d</option>
                      <option value="30d">Last 30d</option>
                    </select>
                  </div>
                </div>
              )}

              {builderState.step === 3 && (
                <div className="db-builder-step3">
                  <p className="db-builder-hint">Preview:</p>
                  <div className="db-builder-preview">
                    <div className="db-widget" style={{ height: '200px' }}>
                      <div className="db-widget-header">
                        <span className="db-widget-title">
                          {builderState.title || (builderState.selectedType ? WIDGET_TYPE_LABELS[builderState.selectedType] : 'Widget')}
                        </span>
                      </div>
                      <div className="db-widget-content" style={{ height: 'calc(100% - 36px)' }}>
                        {builderState.selectedType && renderWidgetContent({ i: 'preview', x: 0, y: 0, w: 4, h: 3, type: builderState.selectedType, title: '' })}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="db-modal-footer">
              {builderState.step > 1 && (
                <button
                  className="db-btn"
                  onClick={() => setBuilderState({ ...builderState, step: (builderState.step - 1) as 1 | 2 | 3 })}
                >
                  ← Back
                </button>
              )}
              {builderState.step < 3 ? (
                <button
                  className="db-btn db-btn-primary"
                  disabled={builderState.step === 1 && !builderState.selectedType}
                  onClick={() => setBuilderState({ ...builderState, step: (builderState.step + 1) as 1 | 2 | 3 })}
                >
                  Next →
                </button>
              ) : (
                <button className="db-btn db-btn-primary" onClick={handleAddWidget}>
                  Add to Dashboard
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
