/**
 * MCPKeysTab - Gestione API key personali per il server MCP (/api/mcp).
 *
 * Le chiavi autenticano gli agenti AI (Claude, ecc.) via
 * `Authorization: Bearer fd_...` e impersonano l'utente proprietario.
 * La chiave in chiaro è visibile solo alla creazione.
 */
import React, { useCallback, useEffect, useState } from 'react';
import api, { MCPAPIKey } from '../../services/api';

function MCPKeysTab() {
  const [keys, setKeys] = useState<MCPAPIKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyExpiry, setNewKeyExpiry] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Chiave appena creata: mostrata una sola volta
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [hasCopied, setHasCopied] = useState(false);

  const loadKeys = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.getMCPAPIKeys();
      setKeys(data);
    } catch {
      setError('Errore nel caricamento delle chiavi MCP');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const handleCreate = async () => {
    if (!newKeyName.trim()) {
      setError('Inserisci un nome per la chiave');
      return;
    }
    try {
      setIsCreating(true);
      setError(null);
      const payload: { name: string; expires_at?: string } = { name: newKeyName.trim() };
      if (newKeyExpiry) {
        payload.expires_at = new Date(newKeyExpiry).toISOString();
      }
      const response = await api.createMCPAPIKey(payload);
      setCreatedKey(response.key);
      setHasCopied(false);
      setNewKeyName('');
      setNewKeyExpiry('');
      loadKeys();
    } catch {
      setError('Errore nella creazione della chiave');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await api.revokeMCPAPIKey(id);
      loadKeys();
    } catch {
      setError('Errore nella revoca della chiave');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteMCPAPIKey(id);
      loadKeys();
    } catch {
      setError('Errore nell\'eliminazione della chiave');
    }
  };

  const handleCopy = async () => {
    if (!createdKey) return;
    try {
      await navigator.clipboard.writeText(createdKey);
      setHasCopied(true);
    } catch {
      // Clipboard non disponibile (es. HTTP non sicuro): la chiave resta visibile
    }
  };

  const mcpEndpoint = `${window.location.origin}/api/mcp`;

  return (
    <div className="settings-section">
      <div className="section-header-with-action">
        <div>
          <h2 className="section-title">MCP Server</h2>
          <p className="section-description">
            API key personali per collegare agenti AI al server MCP di FireDog
            (protocollo Model Context Protocol, sola lettura)
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Banner one-time con la chiave appena creata */}
      {createdKey && (
        <div className="ssh-key-card" style={{ borderColor: 'var(--color-warning, #f59e0b)' }}>
          <div className="ssh-key-header">
            <div className="ssh-key-info">
              <h3>Chiave creata — copiala ora</h3>
              <p className="section-description">
                Questa chiave non sarà mai più visibile. Salvala in un posto sicuro.
              </p>
            </div>
            <div className="ssh-key-actions">
              <button className="btn btn-primary btn-sm" onClick={handleCopy}>
                {hasCopied ? 'Copiata ✓' : 'Copia'}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setCreatedKey(null)}>
                Chiudi
              </button>
            </div>
          </div>
          <div className="ssh-key-details">
            <code style={{ wordBreak: 'break-all', userSelect: 'all' }}>{createdKey}</code>
          </div>
        </div>
      )}

      {/* Form creazione */}
      <div className="ssh-key-card">
        <div className="ssh-key-header">
          <div className="ssh-key-info" style={{ flex: 1 }}>
            <h3>Nuova chiave</h3>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Nome (es. claude-desktop)"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                maxLength={100}
              />
              <input
                type="datetime-local"
                className="form-input"
                title="Scadenza opzionale"
                value={newKeyExpiry}
                onChange={(e) => setNewKeyExpiry(e.target.value)}
              />
              <button className="btn btn-primary" onClick={handleCreate} disabled={isCreating}>
                {isCreating ? 'Creazione…' : 'Crea chiave'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Lista chiavi */}
      {isLoading ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>Caricamento chiavi MCP...</p>
        </div>
      ) : keys.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
          </svg>
          <h3>Nessuna chiave MCP</h3>
          <p>Crea una chiave per collegare un agente AI a FireDog</p>
        </div>
      ) : (
        <div className="ssh-keys-list">
          {keys.map((key) => (
            <div key={key.id} className="ssh-key-card">
              <div className="ssh-key-header">
                <div className="ssh-key-info">
                  <h3>{key.name}</h3>
                  <div className="ssh-key-meta">
                    <span className={`badge ${key.is_active ? 'badge-success' : 'badge-danger'}`}>
                      {key.is_active ? 'Attiva' : 'Revocata'}
                    </span>
                    <span className="badge badge-secondary">{key.key_prefix}…</span>
                    {key.last_used_at && (
                      <span className="ssh-key-targets">
                        Ultimo uso: {new Date(key.last_used_at).toLocaleString('it-IT')}
                      </span>
                    )}
                  </div>
                </div>
                <div className="ssh-key-actions">
                  {key.is_active && (
                    <button
                      className="btn btn-ghost btn-sm btn-warning"
                      onClick={() => handleRevoke(key.id)}
                      title="Revoca chiave"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
                      </svg>
                    </button>
                  )}
                  <button
                    className="btn btn-ghost btn-sm btn-danger"
                    onClick={() => handleDelete(key.id)}
                    title="Elimina chiave"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="ssh-key-details">
                <div className="ssh-key-created">
                  <label>Creata:</label>
                  <span>{new Date(key.created_at).toLocaleString('it-IT')}</span>
                </div>
                {key.expires_at && (
                  <div className="ssh-key-created">
                    <label>Scade:</label>
                    <span>{new Date(key.expires_at).toLocaleString('it-IT')}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Istruzioni di configurazione client */}
      <div className="ssh-key-card">
        <div className="ssh-key-header">
          <div className="ssh-key-info">
            <h3>Configurazione client MCP</h3>
            <p className="section-description">
              Endpoint JSON-RPC 2.0: <code>{mcpEndpoint}</code> — autenticazione{' '}
              <code>Authorization: Bearer &lt;chiave&gt;</code>
            </p>
          </div>
        </div>
        <div className="ssh-key-details">
          <pre style={{ overflow: 'auto', fontSize: '0.85em' }}>
{`{
  "mcpServers": {
    "firedog": {
      "type": "http",
      "url": "${mcpEndpoint}",
      "headers": { "Authorization": "Bearer fd_<la-tua-chiave>" }
    }
  }
}`}
          </pre>
        </div>
      </div>
    </div>
  );
}

export default MCPKeysTab;
