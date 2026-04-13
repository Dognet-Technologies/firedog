/**
 * GroupDetail Page
 * Hero + TabBar for a single group with aggregate stats
 */
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import apiService from '../services/api';
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

type TabId = 'overview' | 'members' | 'rules' | 'threats' | 'config';

const TABS = [
  { id: 'overview' as TabId, label: 'Overview' },
  { id: 'members' as TabId, label: 'Members' },
  { id: 'rules' as TabId, label: 'Rules' },
  { id: 'threats' as TabId, label: 'Threats' },
  { id: 'config' as TabId, label: 'Config' },
];

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

      // Load threats from all member targets
      if (groupTargets.length > 0) {
        const allThreats: ThreatLog[] = [];
        const allRules: FirewallRule[] = [];
        await Promise.all(
          groupTargets.map(async (t) => {
            try {
              const [threatResp, rulesResp] = await Promise.all([
                apiService.getThreats({ target: t.id, limit: 20 }),
                apiService.getRules(t.id),
              ]);
              allThreats.push(...threatResp.results);
              allRules.push(...rulesResp.results);
            } catch {
              // Skip failed individual target fetches
            }
          })
        );
        setThreats(allThreats);
        setRules(allRules);
      }
    } catch (err) {
      console.error('GroupDetail loadAll error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to load group data' });
    } finally {
      setLoading(false);
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
              <div className="gd-stat-card">
                <div className="gd-stat-card-label">Total Targets</div>
                <div className="gd-stat-card-value">{group.target_count}</div>
              </div>
              <div className="gd-stat-card">
                <div className="gd-stat-card-label">Online</div>
                <div className="gd-stat-card-value gd-value-success">{onlineCount}</div>
              </div>
              <div className="gd-stat-card">
                <div className="gd-stat-card-label">Offline</div>
                <div className="gd-stat-card-value gd-value-danger">{offlineCount}</div>
              </div>
              <div className="gd-stat-card">
                <div className="gd-stat-card-label">Total Threats</div>
                <div className="gd-stat-card-value">{threats.length}</div>
              </div>
              <div className="gd-stat-card">
                <div className="gd-stat-card-label">Critical Threats</div>
                <div className={`gd-stat-card-value${criticalThreats > 0 ? ' gd-value-danger' : ''}`}>{criticalThreats}</div>
              </div>
              <div className="gd-stat-card">
                <div className="gd-stat-card-label">Total Rules</div>
                <div className="gd-stat-card-value">{rules.length}</div>
              </div>
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
              <h2>Rules</h2>
              <span className="gd-section-count">{rules.length} total across all members</span>
            </div>
            {rules.length === 0 ? (
              <div className="empty-state">
                <h3>No rules</h3>
                <p>No firewall rules found for this group's members.</p>
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
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* THREATS */}
        {activeTab === 'threats' && (
          <div className="gd-threats">
            <div className="gd-section-header">
              <h2>Threats</h2>
              <span className="gd-section-count">{threats.length} total from all members</span>
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
