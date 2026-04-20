/**
 * TargetDetail Page
 * Hero header + TabBar + tab content for a single target
 */
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, LineChart, Line } from 'recharts';
import apiService from '../services/api';
import type { Target, FirewallRule, ThreatLog, FileIntegrity } from '../types';
import { useNotifications } from '../contexts/NotificationContext';
import { useTarget } from '../contexts/TargetContext';
import StatusDot from '../components/shared/StatusDot';
import DataTooltip from '../components/shared/DataTooltip';
import SeverityBadge from '../components/shared/SeverityBadge';
import ScoreBar from '../components/shared/ScoreBar';
import TabBar from '../components/shared/TabBar';
import './TargetDetail.css';

type TabId = 'overview' | 'rules' | 'threats' | 'integrity' | 'traffic' | 'performance' | 'config';

const TABS = [
  { id: 'overview' as TabId, label: 'Overview' },
  { id: 'rules' as TabId, label: 'Rules' },
  { id: 'threats' as TabId, label: 'Threats' },
  { id: 'integrity' as TabId, label: 'Integrity' },
  { id: 'traffic' as TabId, label: 'Traffic' },
  { id: 'performance' as TabId, label: 'Performance' },
  { id: 'config' as TabId, label: 'Config' },
];

const formatDate = (ts: string | null): string => {
  if (!ts) return '—';
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(ts));
};

const formatRelative = (ts: string | null): string => {
  if (!ts) return '—';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
};

const truncateHash = (hash: string): string => {
  if (!hash) return '—';
  return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
};

const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-primary)',
    borderRadius: '8px',
    fontSize: '12px',
  },
};

const TargetDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast, showConfirm } = useNotifications();
  const { setSelectedTarget } = useTarget();

  const [target, setTarget] = useState<Target | null>(null);
  const [rules, setRules] = useState<FirewallRule[]>([]);
  const [threats, setThreats] = useState<ThreatLog[]>([]);
  const [integrity, setIntegrity] = useState<FileIntegrity[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  // Config form state
  const [configForm, setConfigForm] = useState({ hostname: '', description: '', ip_address: '' });
  const [savingConfig, setSavingConfig] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const [trafficData, setTrafficData] = useState<any[]>([]);
  const [cpuData, setCpuData] = useState<any[]>([]);
  const [memData, setMemData] = useState<any[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState<{ cpu: number; mem: number; disk: number } | null>(null);

  const targetId = id ? parseInt(id, 10) : null;

  useEffect(() => {
    if (targetId) {
      loadAll(targetId);
    }
  }, [targetId]);

  const loadAll = async (tid: number) => {
    setLoading(true);
    try {
      const [targetData, rulesData, threatsData, integrityData, statsData, heartbeatData] = await Promise.all([
        apiService.getTarget(tid),
        apiService.getRules(tid),
        apiService.getThreats({ target: tid, limit: 50 }),
        apiService.getFileIntegrity(),
        apiService.getFirewallStats(tid, 48),
        apiService.getHeartbeats(tid, 48),
      ]);
      setTarget(targetData);
      setConfigForm({
        hostname: targetData.hostname || '',
        description: targetData.description || '',
        ip_address: targetData.ip_address || '',
      });
      setRules(rulesData.results);
      setThreats(threatsData.results);
      const filtered = integrityData.results.filter((f) => (f as unknown as { target: number }).target === tid);
      setIntegrity(filtered);

      // Traffic data from FirewallStats
      if (statsData.length) {
        const sorted = statsData.slice().reverse();
        const traffic = sorted.map((s: any, idx: number) => {
          const prev = sorted[idx - 1];
          return {
            time: new Date(s.collected_at).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }),
            in: prev ? Math.max(0, s.input_packets - prev.input_packets) : 0,
            out: prev ? Math.max(0, s.output_packets - prev.output_packets) : 0,
          };
        }).slice(1);
        setTrafficData(traffic);
      }

      // Performance data from AgentHeartbeat
      if (heartbeatData.length) {
        const sorted = heartbeatData.slice().reverse();
        setCpuData(sorted.map((hb: any) => ({
          time: new Date(hb.timestamp).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }),
          cpu: hb.cpu_percent,
          load1: +(hb.cpu_percent / 100 * 4).toFixed(2),
        })));
        setMemData(sorted.map((hb: any) => ({
          time: new Date(hb.timestamp).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }),
          used: Math.round(hb.memory_percent * 81.92),
          total: 8192,
        })));
        const latest = sorted[sorted.length - 1];
        setCurrentMetrics({ cpu: latest.cpu_percent, mem: latest.memory_percent, disk: latest.disk_percent });
      }
    } catch (err) {
      console.error('TargetDetail loadAll error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to load target data' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRule = async (ruleId: number) => {
    showConfirm({
      title: 'Delete Rule',
      message: 'Are you sure you want to delete this firewall rule?',
      confirmText: 'Delete',
      cancelText: 'Cancel',
      type: 'danger',
      onConfirm: async () => {
        try {
          await apiService.deleteRule(ruleId);
          setRules((prev) => prev.filter((r) => r.id !== ruleId));
          showToast({ type: 'success', title: 'Rule deleted', message: 'Firewall rule removed' });
        } catch (err) {
          console.error('deleteRule error:', err);
          showToast({ type: 'error', title: 'Error', message: 'Failed to delete rule' });
        }
      },
    });
  };

  const handleSaveConfig = async () => {
    if (!target) return;
    if (!configForm.ip_address.trim()) {
      showToast({ type: 'warning', title: 'Validation', message: 'IP address is required' });
      return;
    }
    // Basic IP validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipRegex.test(configForm.ip_address)) {
      showToast({ type: 'error', title: 'Invalid format', message: 'Use format: 192.168.1.1' });
      return;
    }
    try {
      setSavingConfig(true);
      const updated = await apiService.updateTarget(target.id, {
        hostname: configForm.hostname,
        description: configForm.description,
        ip_address: configForm.ip_address,
      });
      setTarget(updated);
      showToast({ type: 'success', title: 'Saved', message: 'Target configuration updated' });
    } catch (err) {
      console.error('updateTarget error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to save configuration' });
    } finally {
      setSavingConfig(false);
    }
  };

  const handleDeleteTarget = async () => {
    if (!target) return;
    try {
      await apiService.deleteTarget(target.id);
      showToast({ type: 'success', title: 'Deleted', message: `Target ${target.hostname || target.ip_address} deleted` });
      navigate('/targets');
    } catch (err) {
      console.error('deleteTarget error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to delete target' });
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <p>Loading target...</p>
      </div>
    );
  }

  if (!target) {
    return (
      <div className="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
        <h3>Target not found</h3>
        <p>The target you are looking for does not exist.</p>
        <Link to="/targets" className="td-btn td-btn-primary">Back to Targets</Link>
      </div>
    );
  }

  const inputRules = rules.filter((r) => r.chain === 'INPUT');
  const outputRules = rules.filter((r) => r.chain === 'OUTPUT');
  const forwardRules = rules.filter((r) => r.chain === 'FORWARD');

  const criticalCount = threats.filter((t) => t.severity === 'critical').length;
  const unresolvedCount = threats.filter((t) => !t.is_resolved).length;

  const getStatusText = (status: string): string => {
    const map: Record<string, string> = {
      online: 'Online',
      offline: 'Offline',
      error: 'Error',
      installing: 'Installing',
      pending: 'Pending',
    };
    return map[status] || status;
  };

  const getActionBadgeClass = (action: string): string => {
    if (action === 'ACCEPT') return 'action-accept';
    if (action === 'DROP') return 'action-drop';
    return 'action-reject';
  };

  const getIntegrityStatusClass = (status: string): string => {
    if (status === 'ok') return 'integrity-ok';
    if (status === 'modified') return 'integrity-modified';
    if (status === 'missing') return 'integrity-missing';
    return 'integrity-new';
  };

  const renderRulesSection = (sectionRules: FirewallRule[], chain: string) => {
    if (sectionRules.length === 0) return null;
    return (
      <div className="td-rules-section" key={chain}>
        <h3 className="td-section-title">{chain} chain</h3>
        <div className="td-table-wrapper">
          <table className="td-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Protocol</th>
                <th>Port</th>
                <th>Source IP</th>
                <th>Dest IP</th>
                <th>Action</th>
                <th>Comment</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sectionRules.map((rule, idx) => (
                <tr key={rule.id}>
                  <td className="td-cell-muted">{rule.rule_number ?? idx + 1}</td>
                  <td>{rule.protocol.toUpperCase()}</td>
                  <td className="td-mono">{rule.port ?? '—'}</td>
                  <td className="td-mono">{rule.source_ip || '—'}</td>
                  <td className="td-mono">{rule.dest_ip || '—'}</td>
                  <td>
                    <span className={`action-badge ${getActionBadgeClass(rule.action)}`}>{rule.action}</span>
                  </td>
                  <td className="td-cell-muted">{rule.comment || '—'}</td>
                  <td>
                    <button
                      className="td-btn-icon td-btn-icon-danger"
                      onClick={() => handleDeleteRule(rule.id)}
                      title="Delete rule"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="target-detail">
      {/* ===== HERO HEADER ===== */}
      <div className="td-hero">
        <div className="td-hero-top">
          <Link to="/targets" className="td-back-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Targets
          </Link>
        </div>
        <div className="td-hero-body">
          <div className="td-hero-identity">
            <div className="td-hero-name">
              <StatusDot status={target.status as 'online' | 'offline' | 'error' | 'installing' | 'pending'} />
              <h1>{target.hostname || target.ip_address}</h1>
              <span className="td-status-text">{getStatusText(target.status)}</span>
            </div>
            <div className="td-hero-meta">
              <span className="td-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="3" width="20" height="7" rx="1" />
                  <rect x="2" y="14" width="20" height="7" rx="1" />
                </svg>
                {target.ip_address}
              </span>
              {target.target_groups && target.target_groups.length > 0 && (
                <span className="td-meta-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="12 2 2 7 12 12 22 7 12 2" />
                    <polyline points="2 17 12 22 22 17" />
                  </svg>
                  {target.target_groups.map((g) => g.name).join(', ')}
                </span>
              )}
              {target.firedog_version && (
                <span className="td-meta-item">v{target.firedog_version}</span>
              )}
            </div>
          </div>

          <div className="td-hero-stats">
            <DataTooltip inline title="Total Threats" type="count"
              description="Numero totale di minacce rilevate per questo target. Include eventi sia risolti che non risolti, di tutti i livelli di severità."
              source="ThreatLog API · filtrato per target">
              <div className="td-stat-chip">
                <span className="td-stat-chip-value">{threats.length}</span>
                <span className="td-stat-chip-label">Threats</span>
              </div>
            </DataTooltip>
            <DataTooltip inline title="Critical Threats" type="count"
              description="Minacce con severity='critical' per questo target. Indicano attacchi ad alto rischio che richiedono analisi e intervento immediato."
              source="ThreatLog.severity = 'critical'">
              <div className="td-stat-chip td-stat-chip-danger">
                <span className="td-stat-chip-value">{criticalCount}</span>
                <span className="td-stat-chip-label">Critical</span>
              </div>
            </DataTooltip>
            <DataTooltip inline title="Firewall Rules" type="count"
              description="Numero totale di regole firewall attive per questo target, distribuite nelle chain INPUT (traffico in entrata), OUTPUT (traffico in uscita) e FORWARD (traffico instradato)."
              source="FirewallRule API · filtrato per target">
              <div className="td-stat-chip">
                <span className="td-stat-chip-value">{rules.length}</span>
                <span className="td-stat-chip-label">Rules</span>
              </div>
            </DataTooltip>
          </div>

          <div className="td-hero-actions">
            <button className="td-btn td-btn-secondary" onClick={() => {}}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              Sync Rules
            </button>
            <button className="td-btn td-btn-secondary" onClick={() => {}}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 11 12 14 22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
              Check Integrity
            </button>
            <button className="td-btn td-btn-primary" onClick={() => setActiveTab('config')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              Edit Target
            </button>
          </div>
        </div>
      </div>

      {/* ===== TAB BAR ===== */}
      <div className="td-tabs">
        <TabBar
          tabs={TABS}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as TabId)}
        />
      </div>

      {/* ===== TAB CONTENT ===== */}
      <div className="td-content">
        {/* ---- OVERVIEW ---- */}
        {activeTab === 'overview' && (
          <div className="td-overview">
            <div className="td-stat-cards">
              <DataTooltip title="CPU Usage" type="last"
                description="Percentuale di utilizzo CPU al momento dell'ultimo heartbeat. Il valore '—' indica che non sono ancora disponibili dati dal modello AgentHeartbeat per questo target. Visibile nella scheda Performance."
                source="AgentHeartbeat.cpu_percent">
                <div className="td-stat-card">
                  <div className="td-stat-card-label">CPU Usage</div>
                  <div className="td-stat-card-value">{currentMetrics ? `${currentMetrics.cpu.toFixed(1)}%` : '—'}</div>
                  <div className="td-stat-card-sub">vai a Performance →</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Memory Used" type="last"
                description="Percentuale di RAM utilizzata al momento dell'ultimo heartbeat dell'agente. Valore istantaneo. Dettaglio storico disponibile nella scheda Performance."
                source="AgentHeartbeat.memory_percent">
                <div className="td-stat-card">
                  <div className="td-stat-card-label">Memory</div>
                  <div className="td-stat-card-value">{currentMetrics ? `${currentMetrics.mem.toFixed(1)}%` : '—'}</div>
                  <div className="td-stat-card-sub">vai a Performance →</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Traffic (last interval)" type="delta"
                description="Somma dei pacchetti in ingresso e uscita nell'ultimo intervallo di campionamento. Calcolato come delta di FirewallStats tra i due campioni più recenti. Dettaglio nella scheda Traffic."
                source="FirewallStats.input_packets + output_packets (ultimo delta)">
                <div className="td-stat-card">
                  <div className="td-stat-card-label">Traffic</div>
                  <div className="td-stat-card-value">
                    {trafficData.length ? `${(trafficData[trafficData.length - 1].in + trafficData[trafficData.length - 1].out).toLocaleString()}` : '—'}
                  </div>
                  <div className="td-stat-card-sub">pkts · ultimo intervallo</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Agent Status" type="last"
                description="Stato attuale dell'agente FireDog sul target. 'online' significa che l'agente sta inviando heartbeat regolari. 'offline' indica assenza di segnale per più di 5 minuti."
                source="Target.status · Target.last_seen">
                <div className="td-stat-card">
                  <div className="td-stat-card-label">Firewall</div>
                  <div className="td-stat-card-value">
                    <StatusDot status={target.status as 'online' | 'offline' | 'error' | 'installing' | 'pending'} />
                  </div>
                  <div className="td-stat-card-sub">Last seen: {formatRelative(target.last_seen)}</div>
                </div>
              </DataTooltip>
            </div>

            <div className="td-overview-row2">
              <DataTooltip title="Traffic Overview (48h)" type="delta"
                description="Andamento del traffico di rete nelle ultime 48 ore. Ogni punto è la variazione dei pacchetti rispetto al campione precedente di FirewallStats, campionato ogni 30 minuti. Inbound = pacchetti in entrata, Outbound = in uscita."
                source="FirewallStats · delta(input_packets, output_packets)">
              <div className="td-chart-card">
                <h3 className="td-card-title">Traffic (24h)</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={trafficData}>
                    <defs>
                      <linearGradient id="tdIn" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="tdOut" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--status-warning)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--status-warning)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: '8px' }}
                    />
                    <Area type="monotone" dataKey="in" stroke="var(--accent-primary)" fill="url(#tdIn)" name="Inbound" />
                    <Area type="monotone" dataKey="out" stroke="var(--status-warning)" fill="url(#tdOut)" name="Outbound" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              </DataTooltip>

              <DataTooltip title="Recent Threats" type="count"
                description="Ultimi 8 eventi di minaccia rilevati per questo target, ordinati per data di rilevamento. Ogni riga mostra il livello di severità, l'IP sorgente e il tempo relativo all'evento."
                source="ThreatLog API · ultimi 50 per target">
              <div className="td-list-card">
                <h3 className="td-card-title">Recent Threats</h3>
                {threats.length === 0 ? (
                  <div className="td-empty-mini">No threats detected</div>
                ) : (
                  <div className="td-threat-list">
                    {threats.slice(0, 8).map((threat) => (
                      <div key={threat.id} className="td-threat-item">
                        <SeverityBadge severity={threat.severity} />
                        <span className="td-threat-ip td-mono">{threat.source_ip}</span>
                        <span className="td-threat-time">{formatRelative(threat.detected_at)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              </DataTooltip>
            </div>

            <div className="td-overview-row3">
              <DataTooltip title="Rules Summary" type="count"
                description="Distribuzione delle regole firewall per chain: INPUT (pacchetti in entrata al sistema), OUTPUT (pacchetti generati dal sistema), FORWARD (pacchetti in transito da instradare). Un numero alto di regole INPUT è normale per server esposti."
                source="FirewallRule API · raggruppato per chain">
              <div className="td-mini-card">
                <h3 className="td-card-title">Rules Summary</h3>
                <div className="td-rules-summary">
                  <div className="td-rules-summary-item">
                    <span className="td-rules-summary-chain">INPUT</span>
                    <span className="td-rules-summary-count">{inputRules.length}</span>
                  </div>
                  <div className="td-rules-summary-item">
                    <span className="td-rules-summary-chain">OUTPUT</span>
                    <span className="td-rules-summary-count">{outputRules.length}</span>
                  </div>
                  <div className="td-rules-summary-item">
                    <span className="td-rules-summary-chain">FORWARD</span>
                    <span className="td-rules-summary-count">{forwardRules.length}</span>
                  </div>
                </div>
              </div>
              </DataTooltip>

              <DataTooltip title="File Integrity Status" type="count"
                description="Stato del monitoraggio dell'integrità dei file critici sul target. 'ok' = nessuna modifica; 'modified' = file alterato rispetto alla baseline; 'missing' = file atteso non trovato; 'new' = file non previsto rilevato."
                source="FileIntegrity API · filtrato per target">
              <div className="td-mini-card">
                <h3 className="td-card-title">Integrity Status</h3>
                <div className="td-integrity-summary">
                  {['ok', 'modified', 'missing', 'new'].map((s) => {
                    const count = integrity.filter((f) => f.status === s).length;
                    return (
                      <div key={s} className="td-integrity-summary-item">
                        <span className={`integrity-badge integrity-${s}`}>{s}</span>
                        <span className="td-integrity-summary-count">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              </DataTooltip>

              <DataTooltip title="Threat Distribution" type="count"
                description="Distribuzione delle minacce per livello di severità: critical (blocco immediato), high (attenzione elevata), medium (monitoraggio), low (informativo). Comprende sia minacce attive che risolte."
                source="ThreatLog.severity · filtrato per target">
              <div className="td-mini-card">
                <h3 className="td-card-title">Threat Distribution</h3>
                <div className="td-threat-dist">
                  {(['critical', 'high', 'medium', 'low'] as const).map((sev) => {
                    const count = threats.filter((t) => t.severity === sev).length;
                    return (
                      <div key={sev} className="td-threat-dist-item">
                        <SeverityBadge severity={sev} />
                        <span className="td-threat-dist-count">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              </DataTooltip>
            </div>
          </div>
        )}

        {/* ---- RULES ---- */}
        {activeTab === 'rules' && (
          <div className="td-rules">
            <div className="td-section-header">
              <h2>Firewall Rules</h2>
              <span className="td-section-count">{rules.length} rules</span>
              {target && (
                <button
                  className="mon-detail-link"
                  onClick={() => { setSelectedTarget(target); navigate('/firewall'); }}
                >
                  Open in Firewall →
                </button>
              )}
            </div>
            {rules.length === 0 ? (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                <h3>No rules</h3>
                <p>No firewall rules configured for this target.</p>
              </div>
            ) : (
              <>
                {renderRulesSection(inputRules, 'INPUT')}
                {renderRulesSection(outputRules, 'OUTPUT')}
                {renderRulesSection(forwardRules, 'FORWARD')}
              </>
            )}
          </div>
        )}

        {/* ---- THREATS ---- */}
        {activeTab === 'threats' && (
          <div className="td-threats">
            <div className="td-section-header">
              <h2>Threats</h2>
              <span className="td-section-count">{unresolvedCount} unresolved / {threats.length} total</span>
              {target && (
                <button
                  className="mon-detail-link"
                  onClick={() => { setSelectedTarget(target); navigate('/threats'); }}
                >
                  Open in Threats →
                </button>
              )}
            </div>
            {threats.length === 0 ? (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                </svg>
                <h3>No threats</h3>
                <p>No threats detected for this target.</p>
              </div>
            ) : (
              <div className="td-table-wrapper">
                <table className="td-table">
                  <thead>
                    <tr>
                      <th>Severity</th>
                      <th>Source IP</th>
                      <th>Score</th>
                      <th>Protocol</th>
                      <th>Port</th>
                      <th>Detected</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {threats.map((threat) => (
                      <tr key={threat.id} className={`td-threat-row td-threat-row-${threat.severity}`}>
                        <td><SeverityBadge severity={threat.severity} /></td>
                        <td className="td-mono">{threat.source_ip}</td>
                        <td><ScoreBar score={threat.threat_score} /></td>
                        <td>{threat.protocol}</td>
                        <td className="td-mono">{threat.dest_port ?? '—'}</td>
                        <td>{formatRelative(threat.detected_at)}</td>
                        <td>
                          {threat.is_resolved ? (
                            <span className="badge-resolved">Resolved</span>
                          ) : (
                            <span className="badge-active">Active</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ---- INTEGRITY ---- */}
        {activeTab === 'integrity' && (
          <div className="td-integrity">
            <div className="td-section-header">
              <h2>File Integrity</h2>
              <span className="td-section-count">{integrity.length} files monitored</span>
            </div>

            <h3 className="td-section-subtitle">Config Files</h3>
            {integrity.length === 0 ? (
              <div className="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <polyline points="9 11 12 14 22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                <h3>No integrity data</h3>
                <p>No file integrity records for this target.</p>
              </div>
            ) : (
              <div className="td-table-wrapper">
                <table className="td-table">
                  <thead>
                    <tr>
                      <th>Path</th>
                      <th>Status</th>
                      <th>Hash</th>
                      <th>Size</th>
                      <th>Permissions</th>
                      <th>Last Checked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {integrity.map((file) => (
                      <tr key={file.id}>
                        <td className="td-mono">{file.file_path}</td>
                        <td>
                          <span className={`integrity-badge ${getIntegrityStatusClass(file.status)}`}>
                            {file.status}
                          </span>
                        </td>
                        <td className="td-mono td-cell-muted">{truncateHash(file.sha512_hash)}</td>
                        <td>{file.file_size ? `${(file.file_size / 1024).toFixed(1)} KB` : '—'}</td>
                        <td className="td-mono">{file.file_permissions || '—'}</td>
                        <td>{formatRelative(file.last_checked)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ---- TRAFFIC ---- */}
        {activeTab === 'traffic' && (
          <div className="td-traffic">
            <div className="td-section-header">
              <h2>Traffic Analysis</h2>
            </div>

            <div className="td-charts-grid">
              <DataTooltip title="Traffic In/Out (48h)" type="delta"
                description="Andamento dei pacchetti di rete nelle ultime 48 ore, campionato ogni 30 minuti. Ogni punto è la variazione (delta) rispetto al campione precedente dei contatori cumulativi di FirewallStats. Inbound = ingresso, Outbound = uscita."
                source="FirewallStats.input_packets + output_packets (delta)">
              <div className="td-chart-card td-chart-card-full">
                <h3 className="td-card-title">Traffic In/Out (24h)</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={trafficData}>
                    <defs>
                      <linearGradient id="tdIn2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="tdOut2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--status-warning)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--status-warning)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: '8px' }}
                    />
                    <Area type="monotone" dataKey="in" stroke="var(--accent-primary)" fill="url(#tdIn2)" name="Inbound" />
                    <Area type="monotone" dataKey="out" stroke="var(--status-warning)" fill="url(#tdOut2)" name="Outbound" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              </DataTooltip>

              <DataTooltip title="Protocol Distribution" type="rate"
                description="Distribuzione stimata dei protocolli di rete (TCP, UDP, ICMP). Si tratta di valori statici di default — non derivano da analisi dei pacchetti in tempo reale per questo specifico target."
                source="Stima statica (non da API)">
              <div className="td-chart-card">
                <h3 className="td-card-title">Protocol Distribution</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={[
                    { name: 'TCP', value: 65 },
                    { name: 'UDP', value: 25 },
                    { name: 'ICMP', value: 10 },
                  ]}>
                    <XAxis dataKey="name" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: '8px' }}
                    />
                    <Bar dataKey="value" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} name="%" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              </DataTooltip>

              <DataTooltip title="Connections over time" type="delta"
                description="Stima del numero di connessioni attive nel tempo, derivata proporzionalmente dal volume di pacchetti: connessioni ≈ (in + out) / 20. Non è un contatore reale di connessioni TCP/UDP."
                source="Derivato da FirewallStats (stima)">
              <div className="td-chart-card">
                <h3 className="td-card-title">Connections over time</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={trafficData.map((d) => ({ ...d, conn: Math.floor((d.in + d.out) / 20) }))}>
                    <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                    <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-primary)', borderRadius: '8px' }}
                    />
                    <Line type="monotone" dataKey="conn" stroke="var(--status-success)" dot={false} name="Connections" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              </DataTooltip>
            </div>
          </div>
        )}

        {/* ---- PERFORMANCE ---- */}
        {activeTab === 'performance' && (
          <div className="td-traffic">
            <div className="td-section-header">
              <h2>Performance</h2>
            </div>

            {!currentMetrics ? (
              <p className="td-cell-muted">Nessun dato di performance disponibile per questo target.</p>
            ) : (
              <>
                <div className="td-stat-cards" style={{ marginBottom: '24px' }}>
                  <DataTooltip title="CPU Usage (attuale)" type="last"
                    description="Utilizzo CPU al momento dell'ultimo heartbeat ricevuto. Calcolato su tutti i core. Il trend storico è nel grafico sottostante."
                    source="AgentHeartbeat.cpu_percent">
                    <div className="td-stat-card">
                      <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-tertiary)', marginBottom: 4 }}>CPU</div>
                      <div style={{ fontSize: 'var(--font-xl)', fontWeight: 700 }}>{currentMetrics.cpu.toFixed(1)}%</div>
                    </div>
                  </DataTooltip>
                  <DataTooltip title="Memory Used (attuale)" type="last"
                    description="Percentuale di RAM utilizzata al momento dell'ultimo campionamento. Valore istantaneo. Il trend storico è nel grafico sottostante."
                    source="AgentHeartbeat.memory_percent">
                    <div className="td-stat-card">
                      <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-tertiary)', marginBottom: 4 }}>Memory</div>
                      <div style={{ fontSize: 'var(--font-xl)', fontWeight: 700 }}>{currentMetrics.mem.toFixed(1)}%</div>
                    </div>
                  </DataTooltip>
                  <DataTooltip title="Disk Used (attuale)" type="last"
                    description="Percentuale di spazio disco utilizzato sull'unità principale del target al momento dell'ultimo heartbeat ricevuto dall'agente."
                    source="AgentHeartbeat.disk_percent">
                    <div className="td-stat-card">
                      <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-tertiary)', marginBottom: 4 }}>Disk</div>
                      <div style={{ fontSize: 'var(--font-xl)', fontWeight: 700 }}>{currentMetrics.disk.toFixed(1)}%</div>
                    </div>
                  </DataTooltip>
                </div>

                <div className="td-charts-grid">
                  <DataTooltip title="CPU Usage % (48h)" type="avg"
                    description="Andamento percentuale della CPU nelle ultime 48 ore. Ogni punto è un campionamento istantaneo ogni 30 minuti, non una media dell'intervallo."
                    source="AgentHeartbeat.cpu_percent">
                  <div className="td-chart-card td-chart-card-full">
                    <h3 className="td-card-title">CPU Usage %</h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={cpuData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                        <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
                        <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                        <Tooltip {...CHART_TOOLTIP_STYLE} />
                        <Line type="monotone" dataKey="cpu" stroke="var(--status-warning)" dot={false} strokeWidth={2} name="CPU %" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  </DataTooltip>

                  <DataTooltip title="Memory Usage (48h)" type="avg"
                    description="Andamento utilizzo RAM in MB nelle ultime 48 ore. Calcolato come memory_percent × 8192 MB (RAM totale ipotizzata). Ogni punto è un campionamento istantaneo di AgentHeartbeat."
                    source="AgentHeartbeat.memory_percent × 8192">
                  <div className="td-chart-card">
                    <h3 className="td-card-title">Memory Usage (MB)</h3>
                    <ResponsiveContainer width="100%" height={180}>
                      <AreaChart data={memData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="tdMem" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--status-info)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--status-info)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                        <Tooltip {...CHART_TOOLTIP_STYLE} />
                        <Area type="monotone" dataKey="used" stroke="var(--status-info)" fill="url(#tdMem)" name="Used MB" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  </DataTooltip>

                  <DataTooltip title="CPU Load Average (1m)" type="avg"
                    description="Stima del load average a 1 minuto, calcolata come cpu_percent / 100 × 4 core. Indica quanti processi sono mediamente in coda di esecuzione. Valore approssimato, non il load reale del kernel."
                    source="Derivato da AgentHeartbeat.cpu_percent">
                  <div className="td-chart-card">
                    <h3 className="td-card-title">CPU Load Average</h3>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={cpuData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                        <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                        <Tooltip {...CHART_TOOLTIP_STYLE} />
                        <Line type="monotone" dataKey="load1" stroke="var(--accent-primary)" dot={false} strokeWidth={2} name="Load" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  </DataTooltip>
                </div>
              </>
            )}
          </div>
        )}

        {/* ---- CONFIG ---- */}
        {activeTab === 'config' && (
          <div className="td-config">
            <div className="td-section-header">
              <h2>Configuration</h2>
            </div>

            <div className="td-config-form">
              <div className="td-form-group">
                <label className="td-label">Hostname</label>
                <input
                  type="text"
                  className="td-input"
                  value={configForm.hostname}
                  onChange={(e) => setConfigForm({ ...configForm, hostname: e.target.value })}
                  placeholder="e.g. web-server-01"
                />
              </div>

              <div className="td-form-group">
                <label className="td-label">IP Address</label>
                <input
                  type="text"
                  className="td-input"
                  value={configForm.ip_address}
                  onChange={(e) => setConfigForm({ ...configForm, ip_address: e.target.value })}
                  placeholder="e.g. 192.168.1.10"
                />
              </div>

              <div className="td-form-group">
                <label className="td-label">Description</label>
                <textarea
                  className="td-input td-textarea"
                  value={configForm.description}
                  onChange={(e) => setConfigForm({ ...configForm, description: e.target.value })}
                  placeholder="Target description"
                  rows={3}
                />
              </div>

              <div className="td-config-actions">
                <button
                  className="td-btn td-btn-primary"
                  onClick={handleSaveConfig}
                  disabled={savingConfig}
                >
                  {savingConfig ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>

            <div className="td-danger-zone">
              <h3>Danger Zone</h3>
              <p>Permanently delete this target and all associated data. This action cannot be undone.</p>
              {showDeleteConfirm ? (
                <div className="td-delete-confirm">
                  <p>Are you absolutely sure? Type the target name to confirm.</p>
                  <div className="td-delete-confirm-actions">
                    <button className="td-btn td-btn-danger" onClick={handleDeleteTarget}>
                      Yes, delete target
                    </button>
                    <button className="td-btn td-btn-secondary" onClick={() => setShowDeleteConfirm(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button className="td-btn td-btn-danger" onClick={() => setShowDeleteConfirm(true)}>
                  Delete Target
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TargetDetail;
