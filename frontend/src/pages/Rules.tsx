import React, { useState, useEffect } from 'react';
import rulesService, { FirewallRule, AddRuleRequest } from '../services/rules.service';
import './Rules.css';

interface RulesProps {}

const Rules: React.FC<RulesProps> = () => {
  const [targetId, setTargetId] = useState<number | null>(null);
  const [inputRules, setInputRules] = useState<FirewallRule[]>([]);
  const [outputRules, setOutputRules] = useState<FirewallRule[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Modal add rule
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [selectedChain, setSelectedChain] = useState<'INPUT' | 'OUTPUT'>('INPUT');
  const [newRule, setNewRule] = useState<AddRuleRequest>({
    chain: 'INPUT',
    port: 0,
    protocol: 'tcp',
    source_ip: '',
    dest_ip: '',
    comment: '',
  });

  // TODO: Recuperare targetId selezionato dal context o props
  // Per ora uso un placeholder
  useEffect(() => {
    // Simulazione: prendi primo target disponibile
    // In produzione, usare context o props
    setTargetId(1);
  }, []);

  useEffect(() => {
    if (targetId) {
      loadRules();
    }
  }, [targetId]);

  const loadRules = async (refresh: boolean = false) => {
    if (!targetId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await rulesService.getRules(targetId, refresh);
      setInputRules(data.input_rules || []);
      setOutputRules(data.output_rules || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    if (!targetId) return;
    
    setSyncing(true);
    setError(null);
    setSuccess(null);
    
    try {
      const result = await rulesService.syncRules(targetId);
      setSuccess(`Sincronizzate ${result.synced_rules} regole`);
      await loadRules();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!targetId) return;
    
    // Validazione client-side
    if (!newRule.port || newRule.port < 1 || newRule.port > 65535) {
      setError('Porta non valida (1-65535)');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    
    try {
      await rulesService.addRule(targetId, newRule);
      setSuccess(`Regola aggiunta con successo su ${newRule.chain}`);
      setShowAddModal(false);
      resetForm();
      await loadRules();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveRule = async (chain: string, ruleNumber: number) => {
    if (!targetId) return;
    
    if (!window.confirm(`Rimuovere la regola #${ruleNumber} da ${chain}?`)) {
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(null);
    
    try {
      await rulesService.removeRule(targetId, chain, ruleNumber);
      setSuccess(`Regola #${ruleNumber} rimossa da ${chain}`);
      await loadRules();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setNewRule({
      chain: 'INPUT',
      port: 0,
      protocol: 'tcp',
      source_ip: '',
      dest_ip: '',
      comment: '',
    });
  };

  const openAddModal = (chain: 'INPUT' | 'OUTPUT') => {
    setSelectedChain(chain);
    setNewRule({ ...newRule, chain });
    setShowAddModal(true);
    setError(null);
    setSuccess(null);
  };

  const renderRulesTable = (rules: FirewallRule[], chain: string) => {
    if (rules.length === 0) {
      return (
        <div className="no-rules">
          Nessuna regola custom in {chain}
        </div>
      );
    }

    return (
      <table className="rules-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Protocollo</th>
            <th>Porta</th>
            <th>Source IP</th>
            <th>Dest IP</th>
            <th>Azione</th>
            <th>Commento</th>
            <th>Azioni</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule) => (
            <tr key={rule.id}>
              <td className="rule-num">{rule.rule_number}</td>
              <td>
                <span className="protocol-badge">{rule.protocol || 'all'}</span>
              </td>
              <td>{rule.port || '-'}</td>
              <td className="ip-cell">{rule.source_ip || 'any'}</td>
              <td className="ip-cell">{rule.dest_ip || 'any'}</td>
              <td>
                <span className={`action-badge action-${rule.action.toLowerCase()}`}>
                  {rule.action}
                </span>
              </td>
              <td className="comment-cell" title={rule.comment || ''}>
                {rule.comment || '-'}
              </td>
              <td>
                {rule.is_custom && (
                  <button
                    className="btn-remove"
                    onClick={() => handleRemoveRule(chain, rule.rule_number)}
                    disabled={loading}
                  >
                    Rimuovi
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  if (!targetId) {
    return (
      <div className="rules-page">
        <div className="error-message">
          Seleziona un target per visualizzare le regole firewall
        </div>
      </div>
    );
  }

  return (
    <div className="rules-page">
      {/* Header */}
      <div className="page-header">
        <div className="header-left">
          <h1>Firewall Rules</h1>
          <p className="subtitle">Gestione regole iptables INPUT/OUTPUT</p>
        </div>
        <div className="header-actions">
          <button
            className="btn-secondary"
            onClick={() => loadRules(true)}
            disabled={loading || syncing}
          >
            {loading ? 'Caricamento...' : 'Refresh'}
          </button>
          <button
            className="btn-primary"
            onClick={handleSync}
            disabled={loading || syncing}
          >
            {syncing ? 'Sincronizzazione...' : 'Sync da Target'}
          </button>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="alert alert-error">
          <strong>Errore:</strong> {error}
          <button className="alert-close" onClick={() => setError(null)}>×</button>
        </div>
      )}
      
      {success && (
        <div className="alert alert-success">
          <strong>Successo:</strong> {success}
          <button className="alert-close" onClick={() => setSuccess(null)}>×</button>
        </div>
      )}

      {/* INPUT Rules Section */}
      <div className="rules-section">
        <div className="section-header">
          <h2>
            <span className="chain-icon">▶</span> INPUT Rules
          </h2>
          <button
            className="btn-add"
            onClick={() => openAddModal('INPUT')}
            disabled={loading}
          >
            + Aggiungi Regola
          </button>
        </div>
        <div className="rules-container">
          {loading && inputRules.length === 0 ? (
            <div className="loading-spinner">Caricamento...</div>
          ) : (
            renderRulesTable(inputRules, 'INPUT')
          )}
        </div>
      </div>

      {/* OUTPUT Rules Section */}
      <div className="rules-section">
        <div className="section-header">
          <h2>
            <span className="chain-icon">◀</span> OUTPUT Rules
          </h2>
          <button
            className="btn-add"
            onClick={() => openAddModal('OUTPUT')}
            disabled={loading}
          >
            + Aggiungi Regola
          </button>
        </div>
        <div className="rules-container">
          {loading && outputRules.length === 0 ? (
            <div className="loading-spinner">Caricamento...</div>
          ) : (
            renderRulesTable(outputRules, 'OUTPUT')
          )}
        </div>
      </div>

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Aggiungi Regola {selectedChain}</h3>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>×</button>
            </div>
            
            <form onSubmit={handleAddRule} className="add-rule-form">
              <div className="form-group">
                <label htmlFor="port">Porta *</label>
                <input
                  type="number"
                  id="port"
                  min="1"
                  max="65535"
                  required
                  value={newRule.port || ''}
                  onChange={(e) => setNewRule({ ...newRule, port: parseInt(e.target.value) || 0 })}
                  className="form-input"
                  placeholder="es. 8080"
                />
              </div>

              <div className="form-group">
                <label htmlFor="protocol">Protocollo</label>
                <select
                  id="protocol"
                  value={newRule.protocol}
                  onChange={(e) => setNewRule({ ...newRule, protocol: e.target.value as any })}
                  className="form-select"
                >
                  <option value="tcp">TCP</option>
                  <option value="udp">UDP</option>
                  <option value="icmp">ICMP</option>
                </select>
              </div>

              {selectedChain === 'INPUT' && (
                <div className="form-group">
                  <label htmlFor="source_ip">IP Sorgente (opzionale)</label>
                  <input
                    type="text"
                    id="source_ip"
                    value={newRule.source_ip}
                    onChange={(e) => setNewRule({ ...newRule, source_ip: e.target.value })}
                    className="form-input"
                    placeholder="es. 192.168.1.0/24"
                  />
                  <small>Lascia vuoto per accettare da qualsiasi IP</small>
                </div>
              )}

              {selectedChain === 'OUTPUT' && (
                <div className="form-group">
                  <label htmlFor="dest_ip">IP Destinazione (opzionale)</label>
                  <input
                    type="text"
                    id="dest_ip"
                    value={newRule.dest_ip}
                    onChange={(e) => setNewRule({ ...newRule, dest_ip: e.target.value })}
                    className="form-input"
                    placeholder="es. 10.0.1.50"
                  />
                  <small>Lascia vuoto per consentire verso qualsiasi IP</small>
                </div>
              )}

              <div className="form-group">
                <label htmlFor="comment">Commento</label>
                <input
                  type="text"
                  id="comment"
                  maxLength={256}
                  value={newRule.comment}
                  onChange={(e) => setNewRule({ ...newRule, comment: e.target.value })}
                  className="form-input"
                  placeholder="es. Web application"
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowAddModal(false)}
                  disabled={loading}
                >
                  Annulla
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading}
                >
                  {loading ? 'Aggiunta...' : 'Aggiungi Regola'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Rules;
