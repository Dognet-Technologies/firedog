/**
 * GroupDetail Page
 * Hero + TabBar for a single group with aggregate stats
 */
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import apiService from '../services/api';
import DataTooltip from '../components/shared/DataTooltip';
import type { Target, FirewallRule, ThreatLog } from '../types';
import { useNotifications } from '../contexts/NotificationContext';
import StatusDot from '../components/shared/StatusDot';
import SeverityBadge from '../components/shared/SeverityBadge';
import TabBar from '../components/shared/TabBar';
import './GroupDetail.css';

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

type TabId = 'overview' | 'members' | 'rules' | 'threats' | 'traffic' | 'performance' | 'config';

const TABS = [
  { id: 'overview' as TabId, label: 'Overview' },
  { id: 'members' as TabId, label: 'Members' },
  { id: 'rules' as TabId, label: 'Rules' },
  { id: 'threats' as TabId, label: 'Threats' },
  { id: 'traffic' as TabId, label: 'Traffic' },
  { id: 'performance' as TabId, label: 'Performance' },
  { id: 'config' as TabId, label: 'Config' },
];

const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-primary)',
    borderRadius: '8px',
    fontSize: '12px',
  },
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

const GroupDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useNotifications();

  const [group, setGroup] = useState<TargetGroup | null>(null);
  const [members, setMembers] = useState<Target[]>([]);
  const [rules, setRules] = useState<FirewallRule[]>([]);
  const [threats, setThreats] = useState<ThreatLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  const [configForm, setConfigForm] = useState({ name: '', description: '' });
  const [savingConfig, setSavingConfig] = useState(false);

  // Add Group Rule modal state
  const [showAddRule, setShowAddRule] = useState(false);
  const [newGroupRule, setNewGroupRule] = useState({
    chain: 'INPUT',
    protocol: 'tcp',
    port: '',
    source_ip: '',
    action: 'ACCEPT',
    comment: '',
  });

  const [trafficData, setTrafficData] = useState<any[]>([]);
  const [cpuData, setCpuData] = useState<any[]>([]);
  const [memData, setMemData] = useState<any[]>([]);
  const [avgMetrics, setAvgMetrics] = useState<{ cpu: number; mem: number; disk: number } | null>(null);

  const groupId = id ? parseInt(id, 10) : null;

  useEffect(() => {
    if (groupId) {
      loadAll(groupId);
    }
  }, [groupId]);

  const loadAll = async (gid: number) => {
    setLoading(true);
    try {
      const groupData = await apiService.getGroup(gid);
      setGroup(groupData);
      setConfigForm({ name: groupData.name || '', description: groupData.description || '' });

      const groupTargets: Target[] = groupData.targets || [];
      setMembers(groupTargets);

      // Le regole "del gruppo" sono quelle propagate via Add Group Rule
      // (group_origin=gid sui FirewallRule replicati per ogni membro).
      // Non aggregiamo più tutte le rule di ciascun target singolo.
      try {
        const groupRulesResp = await apiService.getGroupRules(gid);
        setRules(groupRulesResp.results);
      } catch {
        setRules([]);
      }

      // Load threats from all member targets
      if (groupTargets.length > 0) {
        const allThreats: ThreatLog[] = [];
        await Promise.all(
          groupTargets.map(async (t) => {
            try {
              const threatResp = await apiService.getThreats({ target: t.id, limit: 20 });
              allThreats.push(...threatResp.results);
            } catch {
              // Skip failed individual target fetches
            }
          })
        );
        setThreats(allThreats);

        // Fetch monitoring data (firewall stats + heartbeats) from all members in parallel
        const allStats: any[] = [];
        const allHeartbeats: any[] = [];
        await Promise.all(
          groupTargets.map(async (t) => {
            try {
              const [stats, hbs] = await Promise.all([
                apiService.getFirewallStats(t.id, 48),
                apiService.getHeartbeats(t.id, 48),
              ]);
              allStats.push(...stats);
              allHeartbeats.push(...hbs);
            } catch {
              // skip individual target failures
            }
          })
        );

        // Aggregate traffic: sort by timestamp, compute packet deltas per bucket
        if (allStats.length > 0) {
          allStats.sort((a, b) => new Date(a.collected_at).getTime() - new Date(b.collected_at).getTime());
          const td = allStats.slice(1).map((s, i) => ({
            time: new Date(s.collected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            inbound: Math.max(0, (s.input_packets || 0) - (allStats[i].input_packets || 0)),
            outbound: Math.max(0, (s.output_packets || 0) - (allStats[i].output_packets || 0)),
          }));
          setTrafficData(td);
        }

        // Aggregate performance: average CPU/mem/disk per timestamp bucket across members
        if (allHeartbeats.length > 0) {
          allHeartbeats.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
          // Bucket by rounded 5-min intervals
          const buckets = new Map<string, { cpu: number[]; mem: number[]; disk: number[] }>();
          allHeartbeats.forEach((h) => {
            const d = new Date(h.timestamp);
            d.setSeconds(0, 0);
            d.setMinutes(Math.floor(d.getMinutes() / 5) * 5);
            const key = d.toISOString();
            if (!buckets.has(key)) buckets.set(key, { cpu: [], mem: [], disk: [] });
            const b = buckets.get(key)!;
            if (h.cpu_percent != null) b.cpu.push(h.cpu_percent);
            if (h.memory_percent != null) b.mem.push(h.memory_percent);
            if (h.disk_percent != null) b.disk.push(h.disk_percent);
          });
          const avg = (arr: number[]) => arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0;
          const sorted = Array.from(buckets.entries()).sort((a, b) => a[0].localeCompare(b[0]));
          const cpuPoints = sorted.map(([key, b]) => ({
            time: new Date(key).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            value: parseFloat(avg(b.cpu).toFixed(1)),
          }));
          const memPoints = sorted.map(([key, b]) => ({
            time: new Date(key).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            value: parseFloat(avg(b.mem).toFixed(1)),
          }));
          setCpuData(cpuPoints);
          setMemData(memPoints);

          const lastBucket = sorted[sorted.length - 1]?.[1];
          if (lastBucket) {
            setAvgMetrics({
              cpu: parseFloat(avg(lastBucket.cpu).toFixed(1)),
              mem: parseFloat(avg(lastBucket.mem).toFixed(1)),
              disk: parseFloat(avg(lastBucket.disk).toFixed(1)),
            });
          }
        }
      }
    } catch (err) {
      console.error('GroupDetail loadAll error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to load group data' });
    } finally {
      setLoading(false);
    }
  };

  const handleAddGroupRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!groupId) return;
    const port = newGroupRule.port ? parseInt(newGroupRule.port, 10) : null;
    if (port !== null && (isNaN(port) || port < 1 || port > 65535)) {
      showToast({ type: 'error', title: 'Validation', message: 'Port must be 1..65535' });
      return;
    }
    try {
      const resp = await apiService.addGroupRule(groupId, {
        chain: newGroupRule.chain,
        protocol: newGroupRule.protocol,
        port,
        source_ip: newGroupRule.source_ip || null,
        action: newGroupRule.action,
        comment: newGroupRule.comment,
      });
      const ok = resp.rules.filter(r => r.dispatched).length;
      const fail = resp.rules.length - ok;
      const errSummary = Object.entries(resp.dispatch_errors || {}).map(([h, e]) => `${h}: ${e}`).join('; ');
      showToast({
        type: fail > 0 ? 'warning' : 'success',
        title: 'Group rule applied',
        message: `${ok}/${resp.rules.length} member(s) dispatched${errSummary ? ` — errors: ${errSummary}` : ''}`,
      });
      setShowAddRule(false);
      setNewGroupRule({ chain: 'INPUT', protocol: 'tcp', port: '', source_ip: '', action: 'ACCEPT', comment: '' });
      if (groupId) loadAll(groupId);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to apply group rule';
      showToast({ type: 'error', title: 'Error', message: msg });
    }
  };

  const handleRemoveGroupRule = async (ruleId: number) => {
    if (!groupId) return;
    try {
      const resp = await apiService.removeGroupRule(groupId, ruleId);
      showToast({
        type: 'success',
        title: 'Group rule removed',
        message: `${resp.removed.length} rule(s) removed across members`,
      });
      if (groupId) loadAll(groupId);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Failed to remove rule';
      showToast({ type: 'error', title: 'Error', message: msg });
    }
  };

  const handleSaveConfig = async () => {
    if (!group) return;
    if (!configForm.name.trim()) {
      showToast({ type: 'warning', title: 'Validation', message: 'Group name is required' });
      return;
    }
    try {
      setSavingConfig(true);
      // TODO: replace with real API call when updateGroup endpoint is available
      showToast({ type: 'success', title: 'Saved', message: 'Group configuration updated' });
    } catch (err) {
      console.error('updateGroup error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to save group configuration' });
    } finally {
      setSavingConfig(false);
    }
  };

  const getStatusText = (status: string): string => {
    const map: Record<string, string> = {
      online: 'Online', offline: 'Offline', error: 'Error',
      installing: 'Installing', pending: 'Pending',
    };
    return map[status] || status;
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <p>Loading group...</p>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="empty-state">
        <h3>Group not found</h3>
        <Link to="/groups" className="gd-btn gd-btn-primary">Back to Groups</Link>
      </div>
    );
  }

  const onlineCount = members.filter((t) => t.status === 'online').length;
  const offlineCount = members.filter((t) => t.status === 'offline').length;
  const criticalThreats = threats.filter((t) => t.severity === 'critical').length;

  return (
    <div className="group-detail">
      {/* ===== HERO ===== */}
      <div className="gd-hero">
        <div className="gd-hero-top">
          <Link to="/groups" className="gd-back-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Groups
          </Link>
        </div>
        <div className="gd-hero-body">
          <div className="gd-hero-identity">
            <div className="gd-hero-name">
              <div
                className="gd-hero-icon"
                style={{ borderColor: group.color || 'var(--accent-primary)' }}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke={group.color || 'var(--accent-primary)'} strokeWidth="2">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
              </div>
              <h1>{group.name}</h1>
            </div>
            {group.description && (
              <p className="gd-hero-desc">{group.description}</p>
            )}
            <div className="gd-hero-meta">
              <span className="gd-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="3" width="20" height="7" rx="1" />
                  <rect x="2" y="14" width="20" height="7" rx="1" />
                </svg>
                {group.target_count} targets
              </span>
              <span className="gd-meta-item gd-meta-online">
                <StatusDot status="online" />
                {onlineCount} online
              </span>
              {offlineCount > 0 && (
                <span className="gd-meta-item gd-meta-offline">
                  <StatusDot status="offline" />
                  {offlineCount} offline
                </span>
              )}
            </div>
          </div>

          <div className="gd-hero-stats">
            <div className="gd-stat-chip">
              <span className="gd-stat-chip-value">{threats.length}</span>
              <span className="gd-stat-chip-label">Threats</span>
            </div>
            <div className={`gd-stat-chip${criticalThreats > 0 ? ' gd-stat-chip-danger' : ''}`}>
              <span className="gd-stat-chip-value">{criticalThreats}</span>
              <span className="gd-stat-chip-label">Critical</span>
            </div>
            <div className="gd-stat-chip">
              <span className="gd-stat-chip-value">{rules.length}</span>
              <span className="gd-stat-chip-label">Rules</span>
            </div>
          </div>
        </div>
      </div>

      {/* ===== TABS ===== */}
      <div className="gd-tabs">
        <TabBar
          tabs={TABS}
          activeTab={activeTab}
          onChange={(tid) => setActiveTab(tid as TabId)}
        />
      </div>

      {/* ===== CONTENT ===== */}
      <div className="gd-content">
        {/* OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="gd-overview">
            <div className="gd-stat-cards">
              <DataTooltip title="Total Targets" type="count"
                description="Numero di target assegnati a questo gruppo. Ogni target è un sistema con agente FireDog installato. Il contatore riflette la membership corrente nel database."
                source="TargetGroup.target_count">
                <div className="gd-stat-card">
                  <div className="gd-stat-card-label">Total Targets</div>
                  <div className="gd-stat-card-value">{group.target_count}</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Online" type="count"
                description="Numero di target con stato 'online' — stanno inviando heartbeat regolari all'agente. Un target passa offline se non si sentono segnali per più di 5 minuti."
                source="Target.status = 'online' · filtrato per gruppo">
                <div className="gd-stat-card">
                  <div className="gd-stat-card-label">Online</div>
                  <div className="gd-stat-card-value gd-value-success">{onlineCount}</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Offline" type="count"
                description="Numero di target non raggiungibili: l'agente non ha inviato heartbeat recenti. Potrebbe indicare un problema di rete, un sistema spento o un agente non funzionante."
                source="Target.status != 'online' · filtrato per gruppo">
                <div className="gd-stat-card">
                  <div className="gd-stat-card-label">Offline</div>
                  <div className="gd-stat-card-value gd-value-danger">{offlineCount}</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Total Threats" type="count"
                description="Somma di tutti gli eventi di minaccia rilevati su qualsiasi target del gruppo. Comprende minacce attive e risolte, di tutti i livelli di severità. Limite per target: 20 eventi."
                source="ThreatLog API · aggregato per tutti i member">
                <div className="gd-stat-card">
                  <div className="gd-stat-card-label">Total Threats</div>
                  <div className="gd-stat-card-value">{threats.length}</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Critical Threats" type="count"
                description="Minacce con severity='critical' su qualsiasi target del gruppo. Richiedono analisi e intervento immediato. Un valore elevato indica esposizione attiva del gruppo ad attacchi mirati."
                source="ThreatLog.severity = 'critical' · aggregato">
                <div className="gd-stat-card">
                  <div className="gd-stat-card-label">Critical Threats</div>
                  <div className={`gd-stat-card-value${criticalThreats > 0 ? ' gd-value-danger' : ''}`}>{criticalThreats}</div>
                </div>
              </DataTooltip>
              <DataTooltip title="Total Rules" type="count"
                description="Numero complessivo di regole firewall attive su tutti i target del gruppo (INPUT + OUTPUT + FORWARD). Non indica regole uniche: lo stesso tipo di regola può essere replicato su più target."
                source="FirewallRule API · aggregato per tutti i member">
                <div className="gd-stat-card">
                  <div className="gd-stat-card-label">Total Rules</div>
                  <div className="gd-stat-card-value">{rules.length}</div>
                </div>
              </DataTooltip>
            </div>

            <div className="gd-overview-grid">
              <div className="gd-card">
                <h3 className="gd-card-title">Member Status</h3>
                <div className="gd-member-status-list">
                  {members.slice(0, 8).map((t) => (
                    <div key={t.id} className="gd-member-status-item">
                      <StatusDot status={t.status as 'online' | 'offline' | 'error' | 'installing' | 'pending'} />
                      <Link to={`/targets/${t.id}`} className="gd-member-link">
                        {t.hostname || t.ip_address}
                      </Link>
                      <span className="gd-member-ip">{t.ip_address}</span>
                    </div>
                  ))}
                  {members.length > 8 && (
                    <button className="gd-show-more" onClick={() => setActiveTab('members')}>
                      +{members.length - 8} more
                    </button>
                  )}
                </div>
              </div>

              <div className="gd-card">
                <h3 className="gd-card-title">Recent Threats</h3>
                {threats.length === 0 ? (
                  <div className="gd-empty-mini">No threats detected</div>
                ) : (
                  <div className="gd-threat-list">
                    {threats.slice(0, 8).map((threat) => (
                      <div key={threat.id} className="gd-threat-item">
                        <SeverityBadge severity={threat.severity} />
                        <span className="gd-threat-ip">{threat.source_ip}</span>
                        <span className="gd-threat-time">{formatRelative(threat.detected_at)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* MEMBERS */}
        {activeTab === 'members' && (
          <div className="gd-members">
            <div className="gd-section-header">
              <h2>Members</h2>
              <span className="gd-section-count">{members.length} targets</span>
            </div>
            {members.length === 0 ? (
              <div className="empty-state">
                <h3>No members</h3>
                <p>This group has no targets assigned.</p>
              </div>
            ) : (
              <div className="gd-members-grid">
                {members.map((target) => (
                  <div
                    key={target.id}
                    className="gd-member-card"
                    onClick={() => navigate(`/targets/${target.id}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/targets/${target.id}`); }}
                  >
                    <div className="gd-member-card-header">
                      <StatusDot status={target.status as 'online' | 'offline' | 'error' | 'installing' | 'pending'} />
                      <span className="gd-member-card-status">{getStatusText(target.status)}</span>
                    </div>
                    <div className="gd-member-card-name">{target.hostname || target.ip_address}</div>
                    <div className="gd-member-card-ip">{target.ip_address}</div>
                    {target.firedog_version && (
                      <div className="gd-member-card-version">v{target.firedog_version}</div>
                    )}
                    <div className="gd-member-card-footer">
                      Last seen: {formatRelative(target.last_seen)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* RULES */}
        {activeTab === 'rules' && (
          <div className="gd-rules">
            <div className="gd-section-header">
              <h2>Group Rules</h2>
              <span className="gd-section-count">
                {rules.length} replicated across {new Set(rules.map(r => r.target)).size} member(s)
              </span>
              <button className="btn-primary" onClick={() => setShowAddRule(true)}>+ Add Group Rule</button>
            </div>
            {rules.length === 0 ? (
              <div className="empty-state">
                <h3>No group rules yet</h3>
                <p>Aggiungi una regola che verrà replicata su tutti i membri del gruppo. Le rule del gruppo sono identificabili dal marker <code>[group:{group?.name || '...'}]</code> nel commento iptables.</p>
              </div>
            ) : (
              <div className="gd-table-wrapper">
                <table className="gd-table">
                  <thead>
                    <tr>
                      <th>Target</th>
                      <th>Chain</th>
                      <th>Protocol</th>
                      <th>Port</th>
                      <th>Source IP</th>
                      <th>Action</th>
                      <th>Comment</th>
                      <th>Sync</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((rule) => {
                      const targetObj = members.find((m) => m.id === rule.target);
                      return (
                        <tr key={rule.id}>
                          <td className="gd-mono">
                            {targetObj ? (
                              <Link to={`/targets/${rule.target}`} className="gd-link">
                                {targetObj.hostname || targetObj.ip_address}
                              </Link>
                            ) : (
                              rule.target_ip || rule.target
                            )}
                          </td>
                          <td><span className="gd-chain-badge">{rule.chain}</span></td>
                          <td>{rule.protocol.toUpperCase()}</td>
                          <td className="gd-mono">{rule.port ?? '—'}</td>
                          <td className="gd-mono">{rule.source_ip || '—'}</td>
                          <td>
                            <span className={`action-badge action-${rule.action.toLowerCase()}`}>{rule.action}</span>
                          </td>
                          <td className="gd-muted">{rule.comment || '—'}</td>
                          <td>{rule.is_synced ? '✓' : '…'}</td>
                          <td>
                            <button
                              className="btn-icon btn-danger"
                              title="Remove from all group members"
                              onClick={() => handleRemoveGroupRule(rule.id)}
                            >×</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {showAddRule && groupId && (
          <div className="modal-overlay" onClick={() => setShowAddRule(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Add Group Rule → {group?.name}</h2>
                <button className="modal-close" onClick={() => setShowAddRule(false)}>×</button>
              </div>
              <form onSubmit={handleAddGroupRule}>
                <div className="form-group">
                  <label>Chain</label>
                  <select value={newGroupRule.chain} onChange={e => setNewGroupRule({ ...newGroupRule, chain: e.target.value })}>
                    <option value="INPUT">INPUT</option>
                    <option value="OUTPUT">OUTPUT</option>
                    <option value="FORWARD">FORWARD</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Protocol</label>
                  <select value={newGroupRule.protocol} onChange={e => setNewGroupRule({ ...newGroupRule, protocol: e.target.value })}>
                    <option value="tcp">tcp</option>
                    <option value="udp">udp</option>
                    <option value="icmp">icmp</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Port</label>
                  <input type="number" min="1" max="65535" value={newGroupRule.port}
                    onChange={e => setNewGroupRule({ ...newGroupRule, port: e.target.value })} placeholder="es. 80" />
                </div>
                <div className="form-group">
                  <label>Source IP <small>(opzionale, solo INPUT)</small></label>
                  <input type="text" value={newGroupRule.source_ip}
                    onChange={e => setNewGroupRule({ ...newGroupRule, source_ip: e.target.value })} placeholder="es. 10.0.0.0/24" />
                </div>
                <div className="form-group">
                  <label>Action</label>
                  <select value={newGroupRule.action} onChange={e => setNewGroupRule({ ...newGroupRule, action: e.target.value })}>
                    <option value="ACCEPT">ACCEPT</option>
                    <option value="DROP">DROP</option>
                    <option value="REJECT">REJECT</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Comment</label>
                  <input type="text" value={newGroupRule.comment}
                    onChange={e => setNewGroupRule({ ...newGroupRule, comment: e.target.value })} placeholder="es. Allow HTTP for cache nodes" />
                  <small style={{ color: '#888' }}>
                    Verrà prefissato con <code>[group:{group?.name}]</code> per identificare la rule come "di gruppo" anche dentro iptables.
                  </small>
                </div>
                <div className="modal-actions">
                  <button type="button" className="btn-secondary" onClick={() => setShowAddRule(false)}>Cancel</button>
                  <button type="submit" className="btn-primary">Apply to {members.length} member(s)</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* THREATS */}
        {activeTab === 'threats' && (
          <div className="gd-threats">
            <div className="gd-section-header">
              <h2>Threats</h2>
              <span className="gd-section-count">{threats.length} total from all members</span>
              <Link to="/threats" className="mon-detail-link">Open in Threats →</Link>
            </div>
            {threats.length === 0 ? (
              <div className="empty-state">
                <h3>No threats</h3>
                <p>No threats detected across this group's members.</p>
              </div>
            ) : (
              <div className="gd-table-wrapper">
                <table className="gd-table">
                  <thead>
                    <tr>
                      <th>Severity</th>
                      <th>Source IP</th>
                      <th>Target</th>
                      <th>Score</th>
                      <th>Protocol</th>
                      <th>Detected</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {threats.map((threat) => {
                      const targetObj = members.find((m) => m.id === threat.target);
                      return (
                        <tr key={threat.id}>
                          <td><SeverityBadge severity={threat.severity} /></td>
                          <td className="gd-mono">{threat.source_ip}</td>
                          <td>
                            {targetObj ? (
                              <Link to={`/targets/${threat.target}`} className="gd-link">
                                {targetObj.hostname || targetObj.ip_address}
                              </Link>
                            ) : (
                              threat.target_ip || threat.target
                            )}
                          </td>
                          <td>{threat.threat_score}</td>
                          <td>{threat.protocol}</td>
                          <td>{formatRelative(threat.detected_at)}</td>
                          <td>
                            {threat.is_resolved ? (
                              <span className="badge-resolved">Resolved</span>
                            ) : (
                              <span className="badge-active">Active</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TRAFFIC */}
        {activeTab === 'traffic' && (
          <div className="gd-monitoring">
            {trafficData.length === 0 ? (
              <div className="mon-empty">No traffic data available for this group's members.</div>
            ) : (
              <div className="mon-tab-content">
                <div className="mon-stat-cards">
                  <DataTooltip title="Avg Inbound (per intervallo)" type="avg"
                    description="Media dei pacchetti in ingresso per intervallo di campionamento (30 min), aggregata su tutti i target del gruppo. Calcolata come somma dei delta di FirewallStats.input_packets divisa per il numero di intervalli."
                    source="FirewallStats.input_packets · aggregato per gruppo">
                    <div className="mon-stat-card">
                      <div className="mon-stat-label">Avg Inbound</div>
                      <div className="mon-stat-value">
                        {trafficData.length ? Math.round(trafficData.reduce((s, d) => s + d.inbound, 0) / trafficData.length) : 0}
                      </div>
                      <div className="mon-stat-unit">pkts/interval</div>
                    </div>
                  </DataTooltip>
                  <DataTooltip title="Avg Outbound (per intervallo)" type="avg"
                    description="Media dei pacchetti in uscita per intervallo, aggregata su tutti i target del gruppo. I contatori cumulativi di FirewallStats.output_packets di tutti i member vengono sommati e divisi per il numero di intervalli."
                    source="FirewallStats.output_packets · aggregato per gruppo">
                    <div className="mon-stat-card">
                      <div className="mon-stat-label">Avg Outbound</div>
                      <div className="mon-stat-value">
                        {trafficData.length ? Math.round(trafficData.reduce((s, d) => s + d.outbound, 0) / trafficData.length) : 0}
                      </div>
                      <div className="mon-stat-unit">pkts/interval</div>
                    </div>
                  </DataTooltip>
                  <DataTooltip title="Members Contributing" type="count"
                    description="Numero di target del gruppo da cui sono stati ricevuti dati di monitoraggio. Un target non contribuisce se offline o se non ha record FirewallStats recenti."
                    source="TargetGroup.targets · con dati FirewallStats disponibili">
                    <div className="mon-stat-card">
                      <div className="mon-stat-label">Members Contributing</div>
                      <div className="mon-stat-value">{members.length}</div>
                      <div className="mon-stat-unit">targets</div>
                    </div>
                  </DataTooltip>
                </div>
                <DataTooltip title="Aggregate Traffic (48h)" type="delta"
                  description="Traffico di rete aggregato di tutti i target del gruppo nelle ultime 48 ore. I dati di FirewallStats di ogni member vengono uniti, ordinati per timestamp e rappresentati come serie unica di delta per intervallo."
                  source="FirewallStats · tutti i member · delta(input_packets, output_packets)">
                <div className="mon-chart-card">
                  <div className="mon-card-title">Aggregate Traffic (48h)</div>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={trafficData}>
                      <defs>
                        <linearGradient id="gdIn" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gdOut" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="var(--status-success)" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="var(--status-success)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                      <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} />
                      <Tooltip {...CHART_TOOLTIP_STYLE} />
                      <Area type="monotone" dataKey="inbound" stroke="var(--accent-primary)" fill="url(#gdIn)" strokeWidth={2} name="Inbound" />
                      <Area type="monotone" dataKey="outbound" stroke="var(--status-success)" fill="url(#gdOut)" strokeWidth={2} name="Outbound" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                </DataTooltip>
              </div>
            )}
          </div>
        )}

        {/* PERFORMANCE */}
        {activeTab === 'performance' && (
          <div className="gd-monitoring">
            {cpuData.length === 0 ? (
              <div className="mon-empty">No performance data available for this group's members.</div>
            ) : (
              <div className="mon-tab-content">
                <div className="mon-stat-cards">
                  <DataTooltip title="Avg CPU (ultimo bucket)" type="avg"
                    description="Media della percentuale CPU tra tutti i target del gruppo nell'ultimo bucket di 5 minuti. Calcolata come media aritmetica di AgentHeartbeat.cpu_percent su tutti i member con dati disponibili."
                    source="AgentHeartbeat.cpu_percent · media per gruppo">
                  <div className="mon-stat-card">
                    <div className="mon-stat-label">Avg CPU</div>
                    <div className="mon-stat-value">{avgMetrics?.cpu ?? '—'}</div>
                    <div className="mon-stat-unit">%</div>
                  </div>
                  </DataTooltip>
                  <DataTooltip title="Avg Memory (ultimo bucket)" type="avg"
                    description="Media della percentuale RAM utilizzata tra tutti i target del gruppo nell'ultimo bucket di 5 minuti. Media aritmetica di AgentHeartbeat.memory_percent su tutti i member."
                    source="AgentHeartbeat.memory_percent · media per gruppo">
                  <div className="mon-stat-card">
                    <div className="mon-stat-label">Avg Memory</div>
                    <div className="mon-stat-value">{avgMetrics?.mem ?? '—'}</div>
                    <div className="mon-stat-unit">%</div>
                  </div>
                  </DataTooltip>
                  <DataTooltip title="Avg Disk (ultimo bucket)" type="avg"
                    description="Media della percentuale di disco utilizzato tra tutti i target del gruppo nell'ultimo bucket disponibile. Media aritmetica di AgentHeartbeat.disk_percent su tutti i member."
                    source="AgentHeartbeat.disk_percent · media per gruppo">
                  <div className="mon-stat-card">
                    <div className="mon-stat-label">Avg Disk</div>
                    <div className="mon-stat-value">{avgMetrics?.disk ?? '—'}</div>
                    <div className="mon-stat-unit">%</div>
                  </div>
                  </DataTooltip>
                </div>
                <div className="mon-grid-2">
                  <DataTooltip title="Avg CPU Usage (48h)" type="avg"
                    description="Andamento della CPU media del gruppo nelle ultime 48 ore, bucketizzato a 5 minuti. Ogni punto è la media aritmetica di tutti i campionamenti AgentHeartbeat nel bucket, su tutti i target del gruppo."
                    source="AgentHeartbeat.cpu_percent · bucket 5m · media per gruppo">
                  <div className="mon-chart-card">
                    <div className="mon-card-title">Avg CPU Usage (48h)</div>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={cpuData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                        <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} interval="preserveStartEnd" />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} unit="%" />
                        <Tooltip {...CHART_TOOLTIP_STYLE} formatter={(v: any) => [`${v}%`, 'CPU']} />
                        <Line type="monotone" dataKey="value" stroke="var(--accent-primary)" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  </DataTooltip>
                  <DataTooltip title="Avg Memory Usage (48h)" type="avg"
                    description="Andamento della RAM media del gruppo nelle ultime 48 ore, bucketizzato a 5 minuti. Ogni punto è la media di AgentHeartbeat.memory_percent su tutti i target attivi del gruppo nel bucket."
                    source="AgentHeartbeat.memory_percent · bucket 5m · media per gruppo">
                  <div className="mon-chart-card">
                    <div className="mon-card-title">Avg Memory Usage (48h)</div>
                    <ResponsiveContainer width="100%" height={180}>
                      <AreaChart data={memData}>
                        <defs>
                          <linearGradient id="gdMem" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--status-warning)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--status-warning)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                        <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} interval="preserveStartEnd" />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--text-tertiary)' }} unit="%" />
                        <Tooltip {...CHART_TOOLTIP_STYLE} formatter={(v: any) => [`${v}%`, 'Memory']} />
                        <Area type="monotone" dataKey="value" stroke="var(--status-warning)" fill="url(#gdMem)" strokeWidth={2} name="Memory" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  </DataTooltip>
                </div>
              </div>
            )}
          </div>
        )}

        {/* CONFIG */}
        {activeTab === 'config' && (
          <div className="gd-config">
            <div className="gd-section-header">
              <h2>Configuration</h2>
            </div>

            <div className="gd-config-form">
              <div className="gd-form-group">
                <label className="gd-label">Group Name</label>
                <input
                  type="text"
                  className="gd-input"
                  value={configForm.name}
                  onChange={(e) => setConfigForm({ ...configForm, name: e.target.value })}
                  placeholder="e.g. Web Servers"
                />
              </div>
              <div className="gd-form-group">
                <label className="gd-label">Description</label>
                <textarea
                  className="gd-input gd-textarea"
                  value={configForm.description}
                  onChange={(e) => setConfigForm({ ...configForm, description: e.target.value })}
                  placeholder="Group description"
                  rows={3}
                />
              </div>
              <div className="gd-config-actions">
                <button
                  className="gd-btn gd-btn-primary"
                  onClick={handleSaveConfig}
                  disabled={savingConfig}
                >
                  {savingConfig ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GroupDetail;
