/**
 * Notifications Tab Component
 * File: frontend/src/components/Settings/NotificationsTab.tsx
 */
import React, { useState, useEffect } from 'react';
import apiService from '../../services/api';
import { useNotifications } from '../../contexts/NotificationContext';
import type { NotificationConfig, SmtpInfo } from '../../types';

interface NotificationsTabProps {
  onUpdate?: () => void;
}

const NotificationsTab: React.FC<NotificationsTabProps> = ({ onUpdate }) => {
  const { showToast } = useNotifications();
  
  const [config, setConfig] = useState<NotificationConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [showSmtpInfo, setShowSmtpInfo] = useState(false);
  const [smtpInfo, setSmtpInfo] = useState<SmtpInfo | null>(null);
  
  // Form state
  const [formData, setFormData] = useState<Partial<NotificationConfig>>({
    email_enabled: false,
    email_recipients: [],
    smtp_host: 'localhost',
    smtp_port: 587,
    smtp_user: 'microcyber',
    smtp_password: '',
    smtp_use_tls: true,
    smtp_from_email: 'firedog@localhost',
    slack_enabled: false,
    slack_webhook_url: '',
    discord_enabled: false,
    discord_webhook_url: '',
    alert_on_critical_threat: true,
    alert_on_high_threat: true,
    alert_on_target_offline: true,
    target_offline_threshold_minutes: 5,
    alert_on_ssh_error: true,
    alert_on_install_success: false,
    alert_on_install_failed: true,
    cooldown_minutes: 60,
  });
  
  const [emailInput, setEmailInput] = useState('');
  const [testRecipient, setTestRecipient] = useState('');

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await apiService.getNotificationConfig();
      setConfig(data);
      setFormData(data);
    } catch (error: any) {
      console.error('Error loading notification config:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare configurazione notifiche'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      
      // Validazione
      if (formData.email_enabled) {
        if (!formData.email_recipients || formData.email_recipients.length === 0) {
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Inserisci almeno un indirizzo email'
          });
          return;
        }
        
        if (!formData.smtp_host || !formData.smtp_user) {
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Configurazione SMTP incompleta'
          });
          return;
        }
      }
      
      if (formData.slack_enabled && !formData.slack_webhook_url) {
        showToast({
          type: 'error',
          title: 'Errore',
          message: 'Inserisci webhook URL Slack'
        });
        return;
      }
      
      if (formData.discord_enabled && !formData.discord_webhook_url) {
        showToast({
          type: 'error',
          title: 'Errore',
          message: 'Inserisci webhook URL Discord'
        });
        return;
      }
      
      const updated = await apiService.updateNotificationConfig(formData);
      setConfig(updated);
      setFormData(updated);
      
      showToast({
        type: 'success',
        title: 'Successo',
        message: 'Configurazione notifiche salvata'
      });
      
      if (onUpdate) onUpdate();
    } catch (error: any) {
      console.error('Error saving notification config:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: error.response?.data?.message || 'Errore salvataggio configurazione'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (type: 'email' | 'slack' | 'discord') => {
    try {
      setTesting(type);
      
      const data: any = { notification_type: type };
      
      if (type === 'email' && testRecipient) {
        data.test_recipient = testRecipient;
      }
      
      const result = await apiService.testNotification(data);
      
      if (result.success) {
        showToast({
          type: 'success',
          title: 'Test riuscito',
          message: `Notifica ${type} inviata con successo!`
        });
      } else {
        showToast({
          type: 'error',
          title: 'Test fallito',
          message: result.error || 'Errore invio test'
        });
      }
    } catch (error: any) {
      console.error(`Test ${type} error:`, error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: error.response?.data?.error || `Errore test ${type}`
      });
    } finally {
      setTesting(null);
    }
  };

  const addEmailRecipient = () => {
    if (!emailInput.trim()) return;
    
    // Validazione email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(emailInput)) {
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Email non valida'
      });
      return;
    }
    
    const recipients = formData.email_recipients || [];
    
    if (recipients.includes(emailInput)) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Email già presente'
      });
      return;
    }
    
    setFormData({
      ...formData,
      email_recipients: [...recipients, emailInput]
    });
    
    setEmailInput('');
  };

  const removeEmailRecipient = (email: string) => {
    setFormData({
      ...formData,
      email_recipients: (formData.email_recipients || []).filter(e => e !== email)
    });
  };

  const loadSmtpInfo = async () => {
    try {
      const data = await apiService.getSmtpInfo();
      setSmtpInfo(data);
      setShowSmtpInfo(true);
    } catch (error) {
      console.error('Error loading SMTP info:', error);
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Caricamento configurazione...</p>
      </div>
    );
  }

  return (
    <div className="notifications-tab">
      <div className="settings-section">
        <div className="section-header">
          <h3>📧 Email Notifications</h3>
          <button 
            className="btn-link"
            onClick={loadSmtpInfo}
          >
            ℹ️ Guida configurazione SMTP
          </button>
        </div>
        
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.email_enabled || false}
              onChange={e => setFormData({ ...formData, email_enabled: e.target.checked })}
            />
            <span>Abilita notifiche email</span>
          </label>
        </div>

        {formData.email_enabled && (
          <>
            <div className="form-group">
              <label>Destinatari Email</label>
              <div className="email-input-group">
                <input
                  type="email"
                  value={emailInput}
                  onChange={e => setEmailInput(e.target.value)}
                  onKeyPress={e => e.key === 'Enter' && addEmailRecipient()}
                  placeholder="email@example.com"
                  className="form-control"
                />
                <button
                  type="button"
                  onClick={addEmailRecipient}
                  className="btn-primary"
                >
                  Aggiungi
                </button>
              </div>
              
              <div className="email-chips">
                {(formData.email_recipients || []).map((email, index) => (
                  <div key={index} className="chip">
                    <span>{email}</span>
                    <button
                      type="button"
                      onClick={() => removeEmailRecipient(email)}
                      className="chip-remove"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>SMTP Host</label>
                <input
                  type="text"
                  value={formData.smtp_host || ''}
                  onChange={e => setFormData({ ...formData, smtp_host: e.target.value })}
                  placeholder="smtp.gmail.com"
                  className="form-control"
                />
              </div>

              <div className="form-group">
                <label>SMTP Port</label>
                <input
                  type="number"
                  value={formData.smtp_port || 587}
                  onChange={e => setFormData({ ...formData, smtp_port: parseInt(e.target.value) })}
                  className="form-control"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>SMTP Username</label>
                <input
                  type="text"
                  value={formData.smtp_user || ''}
                  onChange={e => setFormData({ ...formData, smtp_user: e.target.value })}
                  placeholder="microcyber"
                  className="form-control"
                />
              </div>

              <div className="form-group">
                <label>SMTP Password</label>
                <input
                  type="password"
                  value={formData.smtp_password || ''}
                  onChange={e => setFormData({ ...formData, smtp_password: e.target.value })}
                  placeholder="••••••••"
                  className="form-control"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Email Mittente</label>
                <input
                  type="email"
                  value={formData.smtp_from_email || ''}
                  onChange={e => setFormData({ ...formData, smtp_from_email: e.target.value })}
                  placeholder="firedog@localhost"
                  className="form-control"
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.smtp_use_tls || false}
                    onChange={e => setFormData({ ...formData, smtp_use_tls: e.target.checked })}
                  />
                  <span>Usa TLS/STARTTLS</span>
                </label>
              </div>
            </div>

            <div className="test-section">
              <div className="form-group">
                <label>Test Email (opzionale)</label>
                <input
                  type="email"
                  value={testRecipient}
                  onChange={e => setTestRecipient(e.target.value)}
                  placeholder="test@example.com"
                  className="form-control"
                />
              </div>
              <button
                type="button"
                onClick={() => handleTest('email')}
                disabled={testing === 'email'}
                className="btn-secondary"
              >
                {testing === 'email' ? 'Invio...' : '📧 Invia Test Email'}
              </button>
            </div>
          </>
        )}
      </div>

      <div className="settings-section">
        <h3>💬 Slack Notifications</h3>
        
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.slack_enabled || false}
              onChange={e => setFormData({ ...formData, slack_enabled: e.target.checked })}
            />
            <span>Abilita notifiche Slack</span>
          </label>
        </div>

        {formData.slack_enabled && (
          <>
            <div className="form-group">
              <label>Webhook URL Slack</label>
              <input
                type="url"
                value={formData.slack_webhook_url || ''}
                onChange={e => setFormData({ ...formData, slack_webhook_url: e.target.value })}
                placeholder="https://hooks.slack.com/services/..."
                className="form-control"
              />
              <small className="form-hint">
                Crea un webhook su: https://api.slack.com/messaging/webhooks
              </small>
            </div>

            <button
              type="button"
              onClick={() => handleTest('slack')}
              disabled={testing === 'slack'}
              className="btn-secondary"
            >
              {testing === 'slack' ? 'Invio...' : '💬 Invia Test Slack'}
            </button>
          </>
        )}
      </div>

      <div className="settings-section">
        <h3>🎮 Discord Notifications</h3>
        
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.discord_enabled || false}
              onChange={e => setFormData({ ...formData, discord_enabled: e.target.checked })}
            />
            <span>Abilita notifiche Discord</span>
          </label>
        </div>

        {formData.discord_enabled && (
          <>
            <div className="form-group">
              <label>Webhook URL Discord</label>
              <input
                type="url"
                value={formData.discord_webhook_url || ''}
                onChange={e => setFormData({ ...formData, discord_webhook_url: e.target.value })}
                placeholder="https://discord.com/api/webhooks/..."
                className="form-control"
              />
              <small className="form-hint">
                Server Settings → Integrations → Webhooks → New Webhook
              </small>
            </div>

            <button
              type="button"
              onClick={() => handleTest('discord')}
              disabled={testing === 'discord'}
              className="btn-secondary"
            >
              {testing === 'discord' ? 'Invio...' : '🎮 Invia Test Discord'}
            </button>
          </>
        )}
      </div>

      <div className="settings-section">
        <h3>🚨 Alert Triggers</h3>
        <p className="section-description">
          Configura quando ricevere notifiche. Gli alert si basano sulla soglia minaccia configurata nelle impostazioni di monitoraggio.
        </p>

        <div className="triggers-grid">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.alert_on_critical_threat || false}
              onChange={e => setFormData({ ...formData, alert_on_critical_threat: e.target.checked })}
            />
            <span>🔴 Minacce critiche</span>
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.alert_on_high_threat || false}
              onChange={e => setFormData({ ...formData, alert_on_high_threat: e.target.checked })}
            />
            <span>🟠 Minacce high</span>
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.alert_on_target_offline || false}
              onChange={e => setFormData({ ...formData, alert_on_target_offline: e.target.checked })}
            />
            <span>📡 Target offline</span>
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.alert_on_ssh_error || false}
              onChange={e => setFormData({ ...formData, alert_on_ssh_error: e.target.checked })}
            />
            <span>🔒 Errori SSH</span>
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.alert_on_install_success || false}
              onChange={e => setFormData({ ...formData, alert_on_install_success: e.target.checked })}
            />
            <span>✅ Installazione completata</span>
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.alert_on_install_failed || false}
              onChange={e => setFormData({ ...formData, alert_on_install_failed: e.target.checked })}
            />
            <span>❌ Installazione fallita</span>
          </label>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Soglia Target Offline (minuti)</label>
            <input
              type="number"
              min="1"
              max="60"
              value={formData.target_offline_threshold_minutes || 5}
              onChange={e => setFormData({ ...formData, target_offline_threshold_minutes: parseInt(e.target.value) })}
              className="form-control"
            />
          </div>

          <div className="form-group">
            <label>Cooldown Notifiche (minuti)</label>
            <input
              type="number"
              min="5"
              max="1440"
              value={formData.cooldown_minutes || 60}
              onChange={e => setFormData({ ...formData, cooldown_minutes: parseInt(e.target.value) })}
              className="form-control"
            />
            <small className="form-hint">
              Intervallo minimo tra notifiche dello stesso tipo
            </small>
          </div>
        </div>
      </div>

      <div className="settings-actions">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="btn-primary"
        >
          {saving ? 'Salvataggio...' : '💾 Salva Configurazione'}
        </button>
      </div>

      {/* Modal SMTP Info */}
      {showSmtpInfo && smtpInfo && (
        <div className="modal-overlay" onClick={() => setShowSmtpInfo(false)}>
          <div className="modal-content modal-large" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{smtpInfo.title}</h3>
              <button className="modal-close" onClick={() => setShowSmtpInfo(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>{smtpInfo.description}</p>

              <h4>Guida Installazione Postfix</h4>
              {smtpInfo.steps.map(step => (
                <div key={step.step} className="smtp-step">
                  <h5>Step {step.step}: {step.title}</h5>
                  <code className="code-block">{step.command}</code>
                  <p>{step.description}</p>
                </div>
              ))}

              <h4>Configurazioni Comuni</h4>
              <div className="smtp-configs-grid">
                {Object.entries(smtpInfo.common_configs).map(([key, cfg]) => (
                  <div key={key} className="smtp-config-card">
                    <h5>{key}</h5>
                    <p className="config-description">{cfg.description}</p>
                    <ul>
                      <li><strong>Host:</strong> {cfg.smtp_host}</li>
                      <li><strong>Port:</strong> {cfg.smtp_port}</li>
                      <li><strong>User:</strong> {cfg.smtp_user}</li>
                      <li><strong>TLS:</strong> {cfg.smtp_use_tls ? 'Sì' : 'No'}</li>
                    </ul>
                  </div>
                ))}
              </div>

              <h4>Troubleshooting</h4>
              <div className="troubleshooting-list">
                {smtpInfo.troubleshooting.map((item, index) => (
                  <div key={index} className="troubleshooting-item">
                    <strong>❌ {item.problem}</strong>
                    <p>✅ {item.solution}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-primary" onClick={() => setShowSmtpInfo(false)}>
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsTab;
