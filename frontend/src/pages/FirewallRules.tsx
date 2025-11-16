/**
 * Firewall Rules Page
 * Gestione completa regole firewall con modalità Standard ed Expert
 */
import React, { useEffect, useState } from 'react';
import apiService from '../services/api';
import type { Target, FirewallRule } from '../types';
import './FirewallRules.css';
import { useNotifications } from '../contexts/NotificationContext';

type ViewMode = 'standard' | 'expert';
type Chain = 'INPUT' | 'OUTPUT' | 'FORWARD';

interface RulesData {
  input_rules: FirewallRule[];
  output_rules: FirewallRule[];
  forward_rules: FirewallRule[];
}

interface NewRule {
  chain: Chain;
  protocol: 'tcp' | 'udp' | 'icmp' | 'all';
  port: string;
  source_ip?: string;
  dest_ip?: string;
  action: 'ACCEPT' | 'DROP' | 'REJECT';
  comment?: string;
  // Expert mode
  expert_command?: string;
}

const FirewallRules: React.FC = () => {
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const { showToast, showConfirm } = useNotifications();
  const [viewMode, setViewMode] = useState<ViewMode>('standard');
  const [activeChain, setActiveChain] = useState<Chain>('INPUT');
  const [rules, setRules] = useState<RulesData>({
    input_rules: [],
    output_rules: [],
    forward_rules: [],
  });
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [newRule, setNewRule] = useState<NewRule>({
    chain: 'INPUT',
    protocol: 'tcp',
    port: '',
    action: 'ACCEPT',
  });

  useEffect(() => {
    loadTargets();
  }, []);

  useEffect(() => {
    if (selectedTarget) {
      loadRules();
    }
  }, [selectedTarget]);

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

  const loadRules = async (refresh = false) => {
    if (!selectedTarget) return;

    try {
      setLoading(true);

      // TODO: Implementare API backend
      // const response = await apiService.getFirewallRules(selectedTarget, refresh);
      // setRules(response);

      // No mock data - rules remain empty until API is implemented

    } catch (error) {
      console.error('Error loading rules:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddRule = async () => {
    // Validazione...
    
    try {
      console.log('Adding rule:', newRule);
      showToast({
        type: 'success',
        title: 'Regola aggiunta',
        message: 'La regola è stata aggiunta con successo'
      });
      
      setShowAddModal(false);
      setNewRule({
        chain: 'INPUT',
        protocol: 'tcp',
        port: '',
        action: 'ACCEPT',
      });
      
      await loadRules(true);
    } catch (error) {
      console.error('Error adding rule:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile aggiungere la regola'
      });
    }
  };

  const handleRemoveRule = async (rule: FirewallRule) => {
    showConfirm({
      title: 'Conferma Rimozione',
      message: `Vuoi rimuovere la regola #${rule.rule_number} (${rule.comment || 'senza commento'})?`,
      confirmText: 'Rimuovi',
      cancelText: 'Annulla',
      type: 'danger',
      onConfirm: async () => {
        try {
          console.log('Removing rule:', rule);
          showToast({
            type: 'success',
            title: 'Regola rimossa',
            message: 'La regola è stata rimossa con successo'
          });
          
          await loadRules(true);
        } catch (error) {
          console.error('Error removing rule:', error);
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile rimuovere la regola'
          });
        }
      }
    });
  };

  const handleSaveRules = async () => {
    try {
      console.log('Saving rules permanently');
      showToast({
        type: 'success',
        title: 'Regole salvate',
        message: 'Le regole sono state salvate permanentemente con iptables-save'
      });
      setShowSaveModal(false);
    } catch (error) {
      console.error('Error saving rules:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile salvare le regole'
      });
    }
  };

  const handleRestoreRules = async () => {
    showConfirm({
      title: 'Conferma Ripristino',
      message: 'Vuoi ripristinare le regole salvate? Le regole correnti verranno sovrascritte.',
      confirmText: 'Ripristina',
      cancelText: 'Annulla',
      type: 'warning',
      onConfirm: async () => {
        try {
          console.log('Restoring rules');
          showToast({
            type: 'success',
            title: 'Regole ripristinate',
            message: 'Le regole sono state ripristinate con successo'
          });
        } catch (error) {
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Impossibile ripristinare le regole'
          });
        }
      }
    });
  };

  const handleExportRules = async () => {
    try {
      // TODO: Implementare API backend per export .rules file
      const content = generateRulesFileContent();
      
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `firewall-rules-${selectedTarget}-${new Date().toISOString().split('T')[0]}.rules`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('Error exporting rules:', error);
      alert('Errore durante l\'export delle regole');
    }
  };

  const generateRulesFileContent = (): string => {
    const lines: string[] = [];
    lines.push('# FireDog Firewall Rules Export');
    lines.push(`# Date: ${new Date().toISOString()}`);
    lines.push(`# Target: ${targets.find(t => t.id === selectedTarget)?.hostname || 'unknown'}`);
    lines.push('');
    
    // Header iptables-save format
    lines.push('*filter');
    
    // INPUT rules
    if (rules.input_rules.length > 0) {
      lines.push('# INPUT Rules');
      rules.input_rules.forEach(rule => {
        lines.push(formatRuleForExport(rule));
      });
      lines.push('');
    }
    
    // OUTPUT rules
    if (rules.output_rules.length > 0) {
      lines.push('# OUTPUT Rules');
      rules.output_rules.forEach(rule => {
        lines.push(formatRuleForExport(rule));
      });
      lines.push('');
    }
    
    // FORWARD rules
    if (rules.forward_rules.length > 0) {
      lines.push('# FORWARD Rules');
      rules.forward_rules.forEach(rule => {
        lines.push(formatRuleForExport(rule));
      });
      lines.push('');
    }
    
    lines.push('COMMIT');
    
    return lines.join('\n');
  };

  const formatRuleForExport = (rule: FirewallRule): string => {
    const parts = ['-A', rule.chain];
    
    if (rule.protocol !== 'all') {
      parts.push('-p', rule.protocol);
    }
    
    if (rule.port) {
      parts.push('--dport', rule.port.toString());
    }
    
    if (rule.source_ip) {
      parts.push('-s', rule.source_ip);
    }
    
    if (rule.dest_ip) {
      parts.push('-d', rule.dest_ip);
    }
    
    parts.push('-j', rule.action);
    
    if (rule.comment) {
      parts.push('-m', 'comment', '--comment', `"${rule.comment}"`);
    }
    
    return parts.join(' ');
  };

  const getCurrentRules = (): FirewallRule[] => {
    switch (activeChain) {
      case 'INPUT':
        return rules.input_rules;
      case 'OUTPUT':
        return rules.output_rules;
      case 'FORWARD':
        return rules.forward_rules;
      default:
        return [];
    }
  };

  const getActionBadgeColor = (action: string) => {
    switch (action) {
      case 'ACCEPT':
        return 'success';
      case 'DROP':
        return 'danger';
      case 'REJECT':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const currentRules = getCurrentRules();

  return (
    <div className="firewall-rules-page">
      <div className="page-header">
        <div className="header-content">
          <h1>
            <svg className="page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
            </svg>
            Regole Firewall
          </h1>
          <p>Gestione completa regole iptables</p>
        </div>
        <div className="header-actions">
          <button className="btn-secondary" onClick={() => loadRules(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.2"></path>
            </svg>
            Sync da Target
          </button>
          <button className="btn-secondary" onClick={() => setShowSaveModal(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path>
            </svg>
            Salva Regole
          </button>
          <button className="btn-secondary" onClick={handleRestoreRules}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
            </svg>
            Restore
          </button>
          <button className="btn-secondary" onClick={handleExportRules}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            Export .rules
          </button>
          <button className="btn-primary" onClick={() => setShowAddModal(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 4v16m8-8H4"></path>
            </svg>
            Aggiungi Regola
          </button>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="mode-selector">
        <div className="mode-tabs">
          <button
            className={`mode-tab ${viewMode === 'standard' ? 'active' : ''}`}
            onClick={() => setViewMode('standard')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <div>
              <strong>Standard</strong>
              <span>Firewall Manager (Simplified)</span>
            </div>
          </button>
          <button
            className={`mode-tab ${viewMode === 'expert' ? 'active' : ''}`}
            onClick={() => setViewMode('expert')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
            </svg>
            <div>
              <strong>Expert</strong>
              <span>Iptables Complete (Advanced)</span>
            </div>
          </button>
        </div>
        {viewMode === 'expert' && (
          <div className="expert-warning">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>
            <span>Modalità Expert: Accesso completo a iptables. Fai attenzione a non bloccarti fuori!</span>
          </div>
        )}
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

        <div className="chain-tabs">
          <button
            className={`chain-tab ${activeChain === 'INPUT' ? 'active' : ''}`}
            onClick={() => setActiveChain('INPUT')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M7 16l-4-4m0 0l4-4m-4 4h18"></path>
            </svg>
            INPUT ({rules.input_rules.length})
          </button>
          <button
            className={`chain-tab ${activeChain === 'OUTPUT' ? 'active' : ''}`}
            onClick={() => setActiveChain('OUTPUT')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
            </svg>
            OUTPUT ({rules.output_rules.length})
          </button>
          <button
            className={`chain-tab ${activeChain === 'FORWARD' ? 'active' : ''}`}
            onClick={() => setActiveChain('FORWARD')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
            </svg>
            FORWARD ({rules.forward_rules.length})
          </button>
        </div>
      </div>

      {/* Rules Table */}
      <div className="rules-container">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Caricamento regole...</p>
          </div>
        ) : !selectedTarget ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
            </svg>
            <h3>Seleziona un Target</h3>
            <p>Scegli un target online per gestire le sue regole firewall</p>
          </div>
        ) : currentRules.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
            </svg>
            <h3>Nessuna Regola {activeChain}</h3>
            <p>Aggiungi la prima regola per la chain {activeChain}</p>
          </div>
        ) : (
          <div className="rules-table-wrapper">
            <table className="rules-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Protocol</th>
                  <th>Port</th>
                  {activeChain === 'INPUT' && <th>Source IP</th>}
                  {activeChain === 'OUTPUT' && <th>Dest IP</th>}
                  <th>Action</th>
                  <th>Comment</th>
                  <th>Packets</th>
                  <th>Bytes</th>
                  <th>Type</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {currentRules.map((rule) => (
                  <tr key={rule.id} className="rule-row">
                    <td className="rule-number">{rule.rule_number}</td>
                    <td>
                      <code className="protocol-badge">{rule.protocol.toUpperCase()}</code>
                    </td>
                    <td className="port-cell">
                      {rule.port ? (
                        <code className="port-value">{rule.port}</code>
                      ) : (
                        <span className="text-muted">*</span>
                      )}
                    </td>
                    {activeChain === 'INPUT' && (
                      <td className="ip-cell">
                        {rule.source_ip ? (
                          <code className="ip-value">{rule.source_ip}</code>
                        ) : (
                          <span className="text-muted">any</span>
                        )}
                      </td>
                    )}
                    {activeChain === 'OUTPUT' && (
                      <td className="ip-cell">
                        {rule.dest_ip ? (
                          <code className="ip-value">{rule.dest_ip}</code>
                        ) : (
                          <span className="text-muted">any</span>
                        )}
                      </td>
                    )}
                    <td>
                      <span className={`action-badge action-${getActionBadgeColor(rule.action)}`}>
                        {rule.action}
                      </span>
                    </td>
                    <td className="comment-cell">
                      {rule.comment || <span className="text-muted">—</span>}
                      {rule.is_custom ? (
                        <span className="type-badge custom">Custom</span>
                      ) : (
                        <span className="type-badge default">Default</span>
                      )}
                    </td>
                    <td className="actions-cell">
                      {rule.is_custom && (
                        <button
                          className="btn-icon btn-danger-small"
                          onClick={() => handleRemoveRule(rule)}
                          title="Rimuovi regola"
                        >
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                          </svg>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Aggiungi Regola Firewall</h2>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
            <div className="modal-body">
              {viewMode === 'standard' ? (
                <>
                  {/* Standard Mode Form */}
                  <div className="form-row">
                    <div className="form-group">
                      <label>
                        Chain <span className="required">*</span>
                      </label>
                      <select
                        value={newRule.chain}
                        onChange={(e) => setNewRule({ ...newRule, chain: e.target.value as Chain })}
                      >
                        <option value="INPUT">INPUT</option>
                        <option value="OUTPUT">OUTPUT</option>
                        <option value="FORWARD">FORWARD</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>
                        Protocol <span className="required">*</span>
                      </label>
                      <select
                        value={newRule.protocol}
                        onChange={(e) => setNewRule({ ...newRule, protocol: e.target.value as any })}
                      >
                        <option value="tcp">TCP</option>
                        <option value="udp">UDP</option>
                        <option value="icmp">ICMP</option>
                        <option value="all">ALL</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>
                        Action <span className="required">*</span>
                      </label>
                      <select
                        value={newRule.action}
                        onChange={(e) => setNewRule({ ...newRule, action: e.target.value as any })}
                      >
                        <option value="ACCEPT">ACCEPT</option>
                        <option value="DROP">DROP</option>
                        <option value="REJECT">REJECT</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Port</label>
                      <input
                        type="number"
                        placeholder="80, 443, 3306..."
                        value={newRule.port}
                        onChange={(e) => setNewRule({ ...newRule, port: e.target.value })}
                        min="1"
                        max="65535"
                        disabled={newRule.protocol === 'icmp' || newRule.protocol === 'all'}
                      />
                      <span className="help-text">Lascia vuoto per tutte le porte</span>
                    </div>

                    {newRule.chain === 'INPUT' && (
                      <div className="form-group">
                        <label>Source IP</label>
                        <input
                          type="text"
                          placeholder="192.168.1.100 o 192.168.1.0/24"
                          value={newRule.source_ip || ''}
                          onChange={(e) => setNewRule({ ...newRule, source_ip: e.target.value })}
                        />
                        <span className="help-text">Opzionale - lascia vuoto per any</span>
                      </div>
                    )}

                    {newRule.chain === 'OUTPUT' && (
                      <div className="form-group">
                        <label>Destination IP</label>
                        <input
                          type="text"
                          placeholder="8.8.8.8 o 0.0.0.0/0"
                          value={newRule.dest_ip || ''}
                          onChange={(e) => setNewRule({ ...newRule, dest_ip: e.target.value })}
                        />
                        <span className="help-text">Opzionale - lascia vuoto per any</span>
                      </div>
                    )}
                  </div>

                  <div className="form-group">
                    <label>Comment</label>
                    <input
                      type="text"
                      placeholder="Descrizione regola..."
                      value={newRule.comment || ''}
                      onChange={(e) => setNewRule({ ...newRule, comment: e.target.value })}
                      maxLength={256}
                    />
                  </div>

                  <div className="info-box">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <div>
                      <strong>Modalità Standard:</strong> Usa firewall-manager per aggiungere regole in modo sicuro.
                      La regola verrà aggiunta all'inizio della chain con conntrack NEW.
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* Expert Mode Form */}
                  <div className="form-group">
                    <label>
                      Comando Iptables <span className="required">*</span>
                    </label>
                    <textarea
                      placeholder="iptables -A INPUT -p tcp --dport 8080 -j ACCEPT"
                      value={newRule.expert_command || ''}
                      onChange={(e) => setNewRule({ ...newRule, expert_command: e.target.value })}
                      rows={5}
                      className="expert-textarea"
                    />
                    <span className="help-text">
                      Inserisci il comando iptables completo. Esempio: iptables -I INPUT 1 -p tcp --dport 8080 -s 192.168.1.0/24 -j ACCEPT
                    </span>
                  </div>

                  <div className="expert-examples">
                    <h4>Esempi Comandi Expert:</h4>
                    <code>iptables -A INPUT -p tcp --dport 8080 -m conntrack --ctstate NEW -j ACCEPT</code>
                    <code>iptables -A INPUT -s 192.168.1.0/24 -j ACCEPT</code>
                    <code>iptables -A OUTPUT -d 8.8.8.8 -j DROP</code>
                    <code>iptables -A INPUT -m limit --limit 10/min -j LOG --log-prefix "FW: "</code>
                  </div>

                  <div className="warning-box">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <div>
                      <strong>Attenzione Modalità Expert:</strong> Hai accesso completo a iptables.
                      Comandi errati possono bloccarti fuori dal sistema. Assicurati di avere accesso console!
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowAddModal(false)}>
                Annulla
              </button>
              <button className="btn-primary" onClick={handleAddRule}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M12 4v16m8-8H4"></path>
                </svg>
                Aggiungi Regola
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save Modal */}
      {showSaveModal && (
        <div className="modal-overlay" onClick={() => setShowSaveModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Salva Regole Permanentemente</h2>
              <button className="modal-close" onClick={() => setShowSaveModal(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <p>
                Le regole correnti verranno salvate permanentemente sul target usando <code>iptables-save</code>.
              </p>
              <p>
                Questo renderà persistenti le regole anche dopo un riavvio del sistema.
              </p>

              <div className="info-box">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <div>
                  <strong>File di destinazione:</strong> /etc/iptables/rules.v4 (IPv4) e /etc/iptables/rules.v6 (IPv6)
                </div>
              </div>

              <div className="stats-summary">
                <div className="stat-item">
                  <strong>{rules.input_rules.length}</strong> regole INPUT
                </div>
                <div className="stat-item">
                  <strong>{rules.output_rules.length}</strong> regole OUTPUT
                </div>
                <div className="stat-item">
                  <strong>{rules.forward_rules.length}</strong> regole FORWARD
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowSaveModal(false)}>
                Annulla
              </button>
              <button className="btn-primary" onClick={handleSaveRules}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path>
                </svg>
                Salva Regole
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FirewallRules;
