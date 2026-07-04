/**
 * Firewall Page — tabbed: Rules | Blocked IPs | Whitelist
 * Migrated from FirewallRules.tsx, BlockedIPs.tsx, Whitelist.tsx
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { FirewallRule, FirewallRuleCreate } from '../types';
import { useTarget } from '../contexts/TargetContext';
import { useNotifications } from '../contexts/NotificationContext';
import PageHeader from '../components/shared/PageHeader';
import TabBar from '../components/shared/TabBar';
import './Firewall.css';

type TabId = 'rules' | 'blocked' | 'whitelist';

const TABS = [
  { id: 'rules' as TabId, label: 'Rules' },
  { id: 'blocked' as TabId, label: 'Blocked IPs' },
  { id: 'whitelist' as TabId, label: 'Whitelist' },
];

// ============================================================
// Local interfaces for BlockedIP and WhitelistEntry
// (API returns these shapes)
// ============================================================

interface BlockedIP {
  id: number;
  ip_address: string;
  block_reason: string;
  block_reason_display: string;
  description: string;
  blocked_by: string;
  blocked_at: string;
  threat_score: number;
  packet_count: number;
  last_attempt?: string;
  expires_at?: string;
  is_active: boolean;
  is_permanent: boolean;
}

interface WhitelistEntry {
  id: number;
  ip_address: string;
  description: string;
  added_by: string;
  added_at: string;
  last_seen?: string;
  hit_count: number;
  is_active: boolean;
}

type Chain = 'INPUT' | 'OUTPUT' | 'FORWARD';

interface NewRuleForm {
  chain: Chain;
  protocol: 'tcp' | 'udp' | 'icmp' | 'all';
  port: string;
  source_ip: string;
  dest_ip: string;
  action: 'ACCEPT' | 'DROP' | 'REJECT';
  comment: string;
}

interface NewBlockForm {
  ip_address: string;
  block_reason: string;
  description: string;
  threat_score: number;
}

interface NewWhitelistForm {
  ip_address: string;
  description: string;
}

const formatDate = (ts: string): string => {
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(ts));
};

// IP validation: accepts x.x.x.x or x.x.x.x/nn
const isValidIPOrCIDR = (val: string): boolean => {
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
  return ipRegex.test(val.trim());
};

const isValidPort = (val: string): boolean => {
  if (!val) return true; // optional
  const n = parseInt(val, 10);
  return !isNaN(n) && n >= 1 && n <= 65535;
};

// ============================================================
// Rules Tab
// ============================================================

const RulesTab: React.FC = () => {
  const { selectedTarget } = useTarget();
  const { showToast, showConfirm } = useNotifications();
  const [rules, setRules] = useState<FirewallRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRule, setNewRule] = useState<NewRuleForm>({
    chain: 'INPUT',
    protocol: 'tcp',
    port: '',
    source_ip: '',
    dest_ip: '',
    action: 'ACCEPT',
    comment: '',
  });

  useEffect(() => {
    if (selectedTarget) loadRules();
  }, [selectedTarget]);

  const loadRules = async () => {
    if (!selectedTarget) return;
    try {
      setLoading(true);
      const resp = await apiService.getRules(selectedTarget.id);
      setRules(resp.results);
    } catch (err) {
      console.error('RulesTab loadRules error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to load rules' });
    } finally {
      setLoading(false);
    }
  };

  const handleAddRule = async () => {
    if (!selectedTarget) return;
    if (newRule.port && !isValidPort(newRule.port)) {
      showToast({ type: 'error', title: 'Validation', message: 'Port must be between 1 and 65535' });
      return;
    }
    if (newRule.source_ip && !isValidIPOrCIDR(newRule.source_ip)) {
      showToast({ type: 'error', title: 'Validation', message: 'Invalid source IP format' });
      return;
    }
    if (newRule.dest_ip && !isValidIPOrCIDR(newRule.dest_ip)) {
      showToast({ type: 'error', title: 'Validation', message: 'Invalid dest IP format' });
      return;
    }
    try {
      const data: FirewallRuleCreate = {
        target: selectedTarget.id,
        chain: newRule.chain,
        protocol: newRule.protocol,
        action: newRule.action,
        comment: newRule.comment || undefined,
      };
      if (newRule.port) data.port = parseInt(newRule.port, 10);
      if (newRule.source_ip) data.source_ip = newRule.source_ip;
      if (newRule.dest_ip) data.dest_ip = newRule.dest_ip;
      await apiService.createRule(data);
      showToast({ type: 'success', title: 'Rule added', message: 'Firewall rule created' });
      setShowAddModal(false);
      setNewRule({ chain: 'INPUT', protocol: 'tcp', port: '', source_ip: '', dest_ip: '', action: 'ACCEPT', comment: '' });
      loadRules();
    } catch (err) {
      console.error('RulesTab handleAddRule error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to add rule' });
    }
  };

  const handleDeleteRule = async (rule: FirewallRule) => {
    showConfirm({
      title: 'Delete Rule',
      message: `Delete rule #${rule.rule_number ?? rule.id}${rule.comment ? ` (${rule.comment})` : ''}?`,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      type: 'danger',
      onConfirm: async () => {
        try {
          await apiService.deleteRule(rule.id);
          setRules((prev) => prev.filter((r) => r.id !== rule.id));
          showToast({ type: 'success', title: 'Deleted', message: 'Rule removed' });
        } catch (err) {
          console.error('deleteRule error:', err);
          showToast({ type: 'error', title: 'Error', message: 'Failed to delete rule' });
        }
      },
    });
  };

  const getActionClass = (action: string) => {
    if (action === 'ACCEPT') return 'fw-action-accept';
    if (action === 'DROP') return 'fw-action-drop';
    return 'fw-action-reject';
  };

  if (!selectedTarget) {
    return (
      <div className="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        <h3>No target selected</h3>
        <p>Select a target from the header to view its rules.</p>
      </div>
    );
  }

  const inputRules = rules.filter((r) => r.chain === 'INPUT');
  const outputRules = rules.filter((r) => r.chain === 'OUTPUT');
  const forwardRules = rules.filter((r) => r.chain === 'FORWARD');

  const renderSection = (sectionRules: FirewallRule[], chain: string) => {
    if (sectionRules.length === 0) return null;
    return (
      <div className="fw-section" key={chain}>
        <h3 className="fw-section-title">{chain} chain ({sectionRules.length})</h3>
        <div className="fw-table-wrapper">
          <table className="fw-table">
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
                  <td className="fw-mono fw-muted">{rule.rule_number ?? idx + 1}</td>
                  <td>{rule.protocol.toUpperCase()}</td>
                  <td className="fw-mono">{rule.port ?? '—'}</td>
                  <td className="fw-mono">{rule.source_ip || '—'}</td>
                  <td className="fw-mono">{rule.dest_ip || '—'}</td>
                  <td><span className={`fw-action ${getActionClass(rule.action)}`}>{rule.action}</span></td>
                  <td className="fw-muted">{rule.comment || '—'}</td>
                  <td>
                    <button className="fw-icon-btn fw-icon-btn-danger" onClick={() => handleDeleteRule(rule)} title="Delete">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6M14 11v6" />
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
    <div className="fw-tab-content">
      <div className="fw-tab-header">
        <span className="fw-tab-count">{rules.length} rules for {selectedTarget.hostname || selectedTarget.ip_address}</span>
        <button className="fw-btn fw-btn-primary" onClick={() => setShowAddModal(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Rule
        </button>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /><p>Loading rules...</p></div>
      ) : rules.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <h3>No rules</h3>
          <p>No firewall rules configured for this target.</p>
        </div>
      ) : (
        <>
          {renderSection(inputRules, 'INPUT')}
          {renderSection(outputRules, 'OUTPUT')}
          {renderSection(forwardRules, 'FORWARD')}
        </>
      )}

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="fw-modal" onClick={(e) => e.stopPropagation()}>
            <div className="fw-modal-header">
              <h3>Add Firewall Rule</h3>
              <button className="fw-modal-close" onClick={() => setShowAddModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="fw-modal-body">
              <div className="fw-form-row">
                <div className="fw-form-group">
                  <label className="fw-label">Chain</label>
                  <select className="fw-input" value={newRule.chain} onChange={(e) => setNewRule({ ...newRule, chain: e.target.value as Chain })}>
                    <option value="INPUT">INPUT</option>
                    <option value="OUTPUT">OUTPUT</option>
                    <option value="FORWARD">FORWARD</option>
                  </select>
                </div>
                <div className="fw-form-group">
                  <label className="fw-label">Protocol</label>
                  <select className="fw-input" value={newRule.protocol} onChange={(e) => setNewRule({ ...newRule, protocol: e.target.value as NewRuleForm['protocol'] })}>
                    <option value="tcp">TCP</option>
                    <option value="udp">UDP</option>
                    <option value="icmp">ICMP</option>
                    <option value="all">ALL</option>
                  </select>
                </div>
                <div className="fw-form-group">
                  <label className="fw-label">Action</label>
                  <select className="fw-input" value={newRule.action} onChange={(e) => setNewRule({ ...newRule, action: e.target.value as NewRuleForm['action'] })}>
                    <option value="ACCEPT">ACCEPT</option>
                    <option value="DROP">DROP</option>
                    <option value="REJECT">REJECT</option>
                  </select>
                </div>
              </div>
              <div className="fw-form-row">
                <div className="fw-form-group">
                  <label className="fw-label">Port <span className="fw-optional">(optional, 1-65535)</span></label>
                  <input type="text" className="fw-input" value={newRule.port} onChange={(e) => setNewRule({ ...newRule, port: e.target.value })} placeholder="e.g. 80" />
                </div>
                <div className="fw-form-group">
                  <label className="fw-label">Source IP <span className="fw-optional">(optional)</span></label>
                  <input type="text" className="fw-input" value={newRule.source_ip} onChange={(e) => setNewRule({ ...newRule, source_ip: e.target.value })} placeholder="e.g. 192.168.1.0/24" />
                </div>
                <div className="fw-form-group">
                  <label className="fw-label">Dest IP <span className="fw-optional">(optional)</span></label>
                  <input type="text" className="fw-input" value={newRule.dest_ip} onChange={(e) => setNewRule({ ...newRule, dest_ip: e.target.value })} placeholder="e.g. 10.0.0.0/8" />
                </div>
              </div>
              <div className="fw-form-group">
                <label className="fw-label">Comment <span className="fw-optional">(optional)</span></label>
                <input type="text" className="fw-input" value={newRule.comment} onChange={(e) => setNewRule({ ...newRule, comment: e.target.value })} placeholder="e.g. Allow HTTP" />
              </div>
            </div>
            <div className="fw-modal-footer">
              <button className="fw-btn fw-btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="fw-btn fw-btn-primary" onClick={handleAddRule}>Add Rule</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// Blocked IPs Tab
// ============================================================

const BlockedIPsTab: React.FC = () => {
  const { selectedTarget } = useTarget();
  const { showToast, showConfirm } = useNotifications();
  const [blockedIPs, setBlockedIPs] = useState<BlockedIP[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterReason, setFilterReason] = useState('all');
  const [newBlock, setNewBlock] = useState<NewBlockForm>({ ip_address: '', block_reason: 'manual', description: '', threat_score: 50 });

  useEffect(() => {
    if (selectedTarget) loadBlockedIPs();
  }, [selectedTarget]);

  const loadBlockedIPs = async () => {
    if (!selectedTarget) return;
    try {
      setLoading(true);
      const resp = await apiService.getBlockedIPsByTarget(selectedTarget.id);
      setBlockedIPs(resp.data?.results || []);
    } catch (err) {
      console.error('BlockedIPsTab loadBlockedIPs error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to load blocked IPs' });
    } finally {
      setLoading(false);
    }
  };

  const handleAddBlock = async () => {
    if (!selectedTarget) return;
    if (!newBlock.ip_address.trim()) {
      showToast({ type: 'warning', title: 'Validation', message: 'Enter an IP address' });
      return;
    }
    if (!isValidIPOrCIDR(newBlock.ip_address)) {
      showToast({ type: 'error', title: 'Invalid format', message: 'Use format: 192.168.1.1' });
      return;
    }
    try {
      await apiService.createBlockedIP({
        target: selectedTarget.id,
        ip_address: newBlock.ip_address,
        block_reason: newBlock.block_reason,
        description: newBlock.description,
        threat_score: newBlock.threat_score,
        blocked_by: 'current_user',
      });
      showToast({ type: 'success', title: 'IP blocked', message: `${newBlock.ip_address} added to blocklist` });
      setShowAddModal(false);
      setNewBlock({ ip_address: '', block_reason: 'manual', description: '', threat_score: 50 });
      loadBlockedIPs();
    } catch (err) {
      console.error('createBlockedIP error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to block IP' });
    }
  };

  const handleUnblock = (id: number, ip: string) => {
    showConfirm({
      title: 'Unblock IP',
      message: `Unblock ${ip}?`,
      confirmText: 'Unblock',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          await apiService.unblockIP(id);
          showToast({ type: 'success', title: 'IP unblocked', message: `${ip} removed from blocklist` });
          loadBlockedIPs();
        } catch (err) {
          console.error('unblockIP error:', err);
          showToast({ type: 'error', title: 'Error', message: 'Failed to unblock IP' });
        }
      },
    });
  };

  const filtered = blockedIPs.filter((b) => {
    const matchSearch = b.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) || b.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchReason = filterReason === 'all' || b.block_reason === filterReason;
    return matchSearch && matchReason;
  });

  if (!selectedTarget) {
    return (
      <div className="empty-state">
        <h3>No target selected</h3>
        <p>Select a target from the header to view blocked IPs.</p>
      </div>
    );
  }

  return (
    <div className="fw-tab-content">
      <div className="fw-tab-header">
        <div className="fw-filter-row">
          <input type="text" className="fw-input fw-search" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search IP or description..." />
          <select className="fw-input" value={filterReason} onChange={(e) => setFilterReason(e.target.value)}>
            <option value="all">All reasons</option>
            <option value="manual">Manual</option>
            <option value="threat_detected">Threat</option>
            <option value="port_scan">Port Scan</option>
            <option value="brute_force">Brute Force</option>
            <option value="syn_flood">SYN Flood</option>
          </select>
        </div>
        <button className="fw-btn fw-btn-primary" onClick={() => setShowAddModal(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
          </svg>
          Block IP
        </button>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <h3>No blocked IPs</h3>
          <p>No blocked IPs{searchTerm ? ' matching your search' : ''} for this target.</p>
        </div>
      ) : (
        <div className="fw-table-wrapper">
          <table className="fw-table">
            <thead>
              <tr>
                <th>IP Address</th>
                <th>Reason</th>
                <th>Description</th>
                <th>Blocked At</th>
                <th>Expires</th>
                <th>Score</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((b) => (
                <tr key={b.id}>
                  <td className="fw-mono">{b.ip_address}</td>
                  <td><span className={`fw-reason-badge fw-reason-${b.block_reason}`}>{b.block_reason_display || b.block_reason}</span></td>
                  <td className="fw-muted">{b.description || '—'}</td>
                  <td className="fw-muted">{formatDate(b.blocked_at)}</td>
                  <td className="fw-muted">{b.expires_at ? formatDate(b.expires_at) : b.is_permanent ? '∞ Permanent' : '—'}</td>
                  <td>{b.threat_score}</td>
                  <td>
                    <button className="fw-btn fw-btn-danger-sm" onClick={() => handleUnblock(b.id, b.ip_address)}>Unblock</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="fw-modal" onClick={(e) => e.stopPropagation()}>
            <div className="fw-modal-header">
              <h3>Block IP Address</h3>
              <button className="fw-modal-close" onClick={() => setShowAddModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="fw-modal-body">
              <div className="fw-form-group">
                <label className="fw-label">IP Address</label>
                <input type="text" className="fw-input" value={newBlock.ip_address} onChange={(e) => setNewBlock({ ...newBlock, ip_address: e.target.value })} placeholder="e.g. 192.168.1.1" />
              </div>
              <div className="fw-form-group">
                <label className="fw-label">Reason</label>
                <select className="fw-input" value={newBlock.block_reason} onChange={(e) => setNewBlock({ ...newBlock, block_reason: e.target.value })}>
                  <option value="manual">Manual</option>
                  <option value="threat_detected">Threat Detected</option>
                  <option value="port_scan">Port Scan</option>
                  <option value="brute_force">Brute Force</option>
                  <option value="syn_flood">SYN Flood</option>
                </select>
              </div>
              <div className="fw-form-group">
                <label className="fw-label">Description <span className="fw-optional">(optional)</span></label>
                <input type="text" className="fw-input" value={newBlock.description} onChange={(e) => setNewBlock({ ...newBlock, description: e.target.value })} placeholder="Reason for blocking" />
              </div>
              <div className="fw-form-group">
                <label className="fw-label">Threat Score: {newBlock.threat_score}</label>
                <input type="range" min={0} max={100} value={newBlock.threat_score} onChange={(e) => setNewBlock({ ...newBlock, threat_score: parseInt(e.target.value, 10) })} />
              </div>
            </div>
            <div className="fw-modal-footer">
              <button className="fw-btn fw-btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="fw-btn fw-btn-primary" onClick={handleAddBlock}>Block IP</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// Whitelist Tab
// ============================================================

const WhitelistTab: React.FC = () => {
  const { selectedTarget } = useTarget();
  const { showToast, showConfirm } = useNotifications();
  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [newEntry, setNewEntry] = useState<NewWhitelistForm>({ ip_address: '', description: '' });

  useEffect(() => {
    if (selectedTarget) loadWhitelist();
  }, [selectedTarget]);

  const loadWhitelist = async () => {
    if (!selectedTarget) return;
    try {
      setLoading(true);
      const resp = await apiService.getWhitelistByTarget(selectedTarget.id);
      setEntries(resp.data?.results || []);
    } catch (err) {
      console.error('WhitelistTab loadWhitelist error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to load whitelist' });
    } finally {
      setLoading(false);
    }
  };

  const handleAddEntry = async () => {
    if (!selectedTarget) return;
    if (!newEntry.ip_address.trim()) {
      showToast({ type: 'warning', title: 'Validation', message: 'Enter an IP address or subnet' });
      return;
    }
    if (!isValidIPOrCIDR(newEntry.ip_address)) {
      showToast({ type: 'error', title: 'Invalid format', message: 'Use format: 192.168.1.1 or 192.168.1.0/24' });
      return;
    }
    try {
      await apiService.createWhitelistEntry({
        target: selectedTarget.id,
        ip_address: newEntry.ip_address,
        description: newEntry.description,
        added_by: 'current_user',
      });
      showToast({ type: 'success', title: 'Added to whitelist', message: `${newEntry.ip_address} whitelisted` });
      setShowAddModal(false);
      setNewEntry({ ip_address: '', description: '' });
      loadWhitelist();
    } catch (err) {
      console.error('createWhitelistEntry error:', err);
      showToast({ type: 'error', title: 'Error', message: 'Failed to add to whitelist' });
    }
  };

  const handleRemoveEntry = (id: number, ip: string) => {
    showConfirm({
      title: 'Remove from Whitelist',
      message: `Remove ${ip} from whitelist?`,
      confirmText: 'Remove',
      cancelText: 'Cancel',
      type: 'danger',
      onConfirm: async () => {
        try {
          await apiService.deleteWhitelistEntry(id);
          showToast({ type: 'success', title: 'Removed', message: `${ip} removed from whitelist` });
          loadWhitelist();
        } catch (err) {
          console.error('deleteWhitelistEntry error:', err);
          showToast({ type: 'error', title: 'Error', message: 'Failed to remove from whitelist' });
        }
      },
    });
  };

  const filtered = entries.filter((e) =>
    e.is_active && (
      e.ip_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.description.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  if (!selectedTarget) {
    return (
      <div className="empty-state">
        <h3>No target selected</h3>
        <p>Select a target from the header to view the whitelist.</p>
      </div>
    );
  }

  const isSubnet = (ip: string) => ip.includes('/');

  return (
    <div className="fw-tab-content">
      <div className="fw-tab-header">
        <input type="text" className="fw-input fw-search" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search IP or description..." />
        <button className="fw-btn fw-btn-primary" onClick={() => setShowAddModal(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Add to Whitelist
        </button>
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner" /></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <h3>Whitelist is empty</h3>
          <p>No whitelisted IPs{searchTerm ? ' matching your search' : ''} for this target.</p>
        </div>
      ) : (
        <div className="fw-table-wrapper">
          <table className="fw-table">
            <thead>
              <tr>
                <th>IP / CIDR</th>
                <th>Description</th>
                <th>Added By</th>
                <th>Added At</th>
                <th>Hits</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => (
                <tr key={entry.id}>
                  <td className="fw-mono">
                    {entry.ip_address}
                    {isSubnet(entry.ip_address) && <span className="fw-subnet-badge">CIDR</span>}
                  </td>
                  <td className="fw-muted">{entry.description || '—'}</td>
                  <td className="fw-muted">{entry.added_by}</td>
                  <td className="fw-muted">{formatDate(entry.added_at)}</td>
                  <td className="fw-mono">{entry.hit_count}</td>
                  <td>
                    <button className="fw-btn fw-btn-danger-sm" onClick={() => handleRemoveEntry(entry.id, entry.ip_address)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="fw-modal" onClick={(e) => e.stopPropagation()}>
            <div className="fw-modal-header">
              <h3>Add to Whitelist</h3>
              <button className="fw-modal-close" onClick={() => setShowAddModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="fw-modal-body">
              <div className="fw-form-group">
                <label className="fw-label">IP Address or Subnet</label>
                <input type="text" className="fw-input" value={newEntry.ip_address} onChange={(e) => setNewEntry({ ...newEntry, ip_address: e.target.value })} placeholder="e.g. 192.168.1.1 or 192.168.1.0/24" />
              </div>
              <div className="fw-form-group">
                <label className="fw-label">Description <span className="fw-optional">(optional)</span></label>
                <input type="text" className="fw-input" value={newEntry.description} onChange={(e) => setNewEntry({ ...newEntry, description: e.target.value })} placeholder="e.g. Office network" />
              </div>
            </div>
            <div className="fw-modal-footer">
              <button className="fw-btn fw-btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button className="fw-btn fw-btn-primary" onClick={handleAddEntry}>Add to Whitelist</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// Main Firewall Page
// ============================================================

const Firewall: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('rules');

  return (
    <div className="firewall-page">
      <PageHeader
        title="Firewall"
        subtitle="Manage rules, blocked IPs, and whitelist"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        }
      />

      <div className="fw-tabs">
        <TabBar tabs={TABS} activeTab={activeTab} onChange={(id) => setActiveTab(id as TabId)} />
      </div>

      {activeTab === 'rules' && <RulesTab />}
      {activeTab === 'blocked' && <BlockedIPsTab />}
      {activeTab === 'whitelist' && <WhitelistTab />}
    </div>
  );
};

export default Firewall;
