/**
 * Settings Page - System Configuration
 */
import React, { useState, useEffect } from 'react';
import './Settings.css';

interface SettingsData {
  // General Settings
  systemName: string;
  timezone: string;
  language: string;
  
  // Appearance Settings
  theme: 'dark' | 'light';
  fontFamily: string;
  fontSize: number;
  borderRadius: number;
  enableAnimations: boolean;
  
  // Notification Settings
  emailNotifications: boolean;
  slackNotifications: boolean;
  discordNotifications: boolean;
  notificationEmail: string;
  notificationWebhook: string;
  
  // Security Settings
  sessionTimeout: number;
  maxLoginAttempts: number;
  enableMFA: boolean;
  
  // Monitoring Settings
  scanInterval: number;
  logRetention: number;
  enableAutoBlock: boolean;
  threatThreshold: number;
}

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'general' | 'appearance' | 'notifications' | 'security' | 'monitoring'>('general');
  const [settings, setSettings] = useState<SettingsData>({
    systemName: 'FireDog Security',
    timezone: 'Europe/Rome',
    language: 'it',
    theme: 'dark',
    fontFamily: 'Inter',
    fontSize: 14,
    borderRadius: 8,
    enableAnimations: true,
    emailNotifications: true,
    slackNotifications: false,
    discordNotifications: false,
    notificationEmail: '',
    notificationWebhook: '',
    sessionTimeout: 30,
    maxLoginAttempts: 5,
    enableMFA: false,
    scanInterval: 60,
    logRetention: 30,
    enableAutoBlock: true,
    threatThreshold: 8,
  });

  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fontOptions = [
    { value: 'Inter', label: 'Inter (Default)' },
    { value: 'Roboto', label: 'Roboto' },
    { value: 'Open Sans', label: 'Open Sans' },
    { value: 'Lato', label: 'Lato' },
    { value: 'Montserrat', label: 'Montserrat' },
  ];

  const languageOptions = [
    { value: 'it', label: '🇮🇹 Italiano' },
    { value: 'en', label: '🇬🇧 English' },
    { value: 'es', label: '🇪🇸 Español' },
    { value: 'fr', label: '🇫🇷 Français' },
    { value: 'de', label: '🇩🇪 Deutsch' },
  ];

  const timezoneOptions = [
    { value: 'Europe/Rome', label: 'Europe/Rome (GMT+1)' },
    { value: 'Europe/London', label: 'Europe/London (GMT)' },
    { value: 'America/New_York', label: 'America/New York (GMT-5)' },
    { value: 'America/Los_Angeles', label: 'America/Los Angeles (GMT-8)' },
    { value: 'Asia/Tokyo', label: 'Asia/Tokyo (GMT+9)' },
  ];

  useEffect(() => {
    // Load settings from localStorage or API
    const savedSettings = localStorage.getItem('firedog_settings');
    if (savedSettings) {
      setSettings(JSON.parse(savedSettings));
    }
  }, []);

  useEffect(() => {
    // Apply font family to document
    document.documentElement.style.setProperty('--font-primary', `'${settings.fontFamily}', sans-serif`);
    document.documentElement.style.setProperty('--font-base', `${settings.fontSize}px`);
    document.documentElement.style.setProperty('--radius-lg', `${settings.borderRadius}px`);
  }, [settings.fontFamily, settings.fontSize, settings.borderRadius]);

  const handleInputChange = (field: keyof SettingsData, value: any) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);

    try {
      // Save to localStorage (in production, this would be an API call)
      localStorage.setItem('firedog_settings', JSON.stringify(settings));
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setSaveMessage({ type: 'success', text: 'Impostazioni salvate con successo!' });
    } catch (error) {
      setSaveMessage({ type: 'error', text: 'Errore nel salvataggio delle impostazioni.' });
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const handleReset = () => {
    if (window.confirm('Sei sicuro di voler ripristinare le impostazioni predefinite?')) {
      localStorage.removeItem('firedog_settings');
      window.location.reload();
    }
  };

  const renderGeneralSettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Impostazioni Generali</h2>
      <p className="section-description">Configura le impostazioni di base del sistema</p>

      <div className="settings-grid">
        <div className="form-group">
          <label htmlFor="systemName">Nome Sistema</label>
          <input
            id="systemName"
            type="text"
            className="input"
            value={settings.systemName}
            onChange={(e) => handleInputChange('systemName', e.target.value)}
          />
          <span className="form-hint">Nome visualizzato nell'interfaccia</span>
        </div>

        <div className="form-group">
          <label htmlFor="timezone">Fuso Orario</label>
          <select
            id="timezone"
            className="input"
            value={settings.timezone}
            onChange={(e) => handleInputChange('timezone', e.target.value)}
          >
            {timezoneOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <span className="form-hint">Fuso orario per i log e le notifiche</span>
        </div>

        <div className="form-group">
          <label htmlFor="language">Lingua</label>
          <select
            id="language"
            className="input"
            value={settings.language}
            onChange={(e) => handleInputChange('language', e.target.value)}
          >
            {languageOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <span className="form-hint">Lingua dell'interfaccia</span>
        </div>
      </div>
    </div>
  );

  const renderAppearanceSettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Aspetto e Personalizzazione</h2>
      <p className="section-description">Personalizza l'aspetto dell'interfaccia</p>

      <div className="settings-grid">
        <div className="form-group">
          <label htmlFor="fontFamily">Font</label>
          <select
            id="fontFamily"
            className="input"
            value={settings.fontFamily}
            onChange={(e) => handleInputChange('fontFamily', e.target.value)}
          >
            {fontOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <span className="form-hint">Font utilizzato nell'interfaccia</span>
        </div>

        <div className="form-group">
          <label htmlFor="fontSize">Dimensione Font: {settings.fontSize}px</label>
          <input
            id="fontSize"
            type="range"
            min="12"
            max="18"
            step="1"
            value={settings.fontSize}
            onChange={(e) => handleInputChange('fontSize', parseInt(e.target.value))}
            className="slider"
          />
          <div className="slider-labels">
            <span>12px</span>
            <span>18px</span>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="borderRadius">Arrotondamento Angoli: {settings.borderRadius}px</label>
          <input
            id="borderRadius"
            type="range"
            min="0"
            max="16"
            step="2"
            value={settings.borderRadius}
            onChange={(e) => handleInputChange('borderRadius', parseInt(e.target.value))}
            className="slider"
          />
          <div className="slider-labels">
            <span>0px (Squadrato)</span>
            <span>16px (Molto Arrotondato)</span>
          </div>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={settings.enableAnimations}
              onChange={(e) => handleInputChange('enableAnimations', e.target.checked)}
            />
            <span>Abilita Animazioni</span>
          </label>
          <span className="form-hint">Attiva/disattiva le animazioni dell'interfaccia</span>
        </div>

        <div className="preview-card">
          <h4>Anteprima Stile</h4>
          <p style={{ fontFamily: settings.fontFamily, fontSize: `${settings.fontSize}px` }}>
            Questo è un esempio di testo con il font selezionato.
          </p>
          <div className="preview-elements">
            <button className="btn btn-primary" style={{ borderRadius: `${settings.borderRadius}px` }}>
              Pulsante Primario
            </button>
            <div className="preview-card-mini" style={{ borderRadius: `${settings.borderRadius}px` }}>
              Card di esempio
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderNotificationSettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Notifiche</h2>
      <p className="section-description">Configura come ricevere le notifiche di sicurezza</p>

      <div className="settings-grid">
        <div className="notification-group">
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={settings.emailNotifications}
                onChange={(e) => handleInputChange('emailNotifications', e.target.checked)}
              />
              <span>Notifiche Email</span>
            </label>
          </div>
          {settings.emailNotifications && (
            <div className="form-group nested">
              <label htmlFor="notificationEmail">Email</label>
              <input
                id="notificationEmail"
                type="email"
                className="input"
                placeholder="admin@example.com"
                value={settings.notificationEmail}
                onChange={(e) => handleInputChange('notificationEmail', e.target.value)}
              />
            </div>
          )}
        </div>

        <div className="notification-group">
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={settings.slackNotifications}
                onChange={(e) => handleInputChange('slackNotifications', e.target.checked)}
              />
              <span>Notifiche Slack</span>
            </label>
          </div>
          {settings.slackNotifications && (
            <div className="form-group nested">
              <label htmlFor="slackWebhook">Slack Webhook URL</label>
              <input
                id="slackWebhook"
                type="url"
                className="input"
                placeholder="https://hooks.slack.com/services/..."
                value={settings.notificationWebhook}
                onChange={(e) => handleInputChange('notificationWebhook', e.target.value)}
              />
            </div>
          )}
        </div>

        <div className="notification-group">
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={settings.discordNotifications}
                onChange={(e) => handleInputChange('discordNotifications', e.target.checked)}
              />
              <span>Notifiche Discord</span>
            </label>
          </div>
          {settings.discordNotifications && (
            <div className="form-group nested">
              <label htmlFor="discordWebhook">Discord Webhook URL</label>
              <input
                id="discordWebhook"
                type="url"
                className="input"
                placeholder="https://discord.com/api/webhooks/..."
                value={settings.notificationWebhook}
                onChange={(e) => handleInputChange('notificationWebhook', e.target.value)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderSecuritySettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Sicurezza</h2>
      <p className="section-description">Configura le impostazioni di sicurezza del sistema</p>

      <div className="settings-grid">
        <div className="form-group">
          <label htmlFor="sessionTimeout">Timeout Sessione (minuti)</label>
          <input
            id="sessionTimeout"
            type="number"
            className="input"
            min="5"
            max="120"
            value={settings.sessionTimeout}
            onChange={(e) => handleInputChange('sessionTimeout', parseInt(e.target.value))}
          />
          <span className="form-hint">Tempo di inattività prima del logout automatico</span>
        </div>

        <div className="form-group">
          <label htmlFor="maxLoginAttempts">Max Tentativi Login</label>
          <input
            id="maxLoginAttempts"
            type="number"
            className="input"
            min="3"
            max="10"
            value={settings.maxLoginAttempts}
            onChange={(e) => handleInputChange('maxLoginAttempts', parseInt(e.target.value))}
          />
          <span className="form-hint">Numero massimo di tentativi prima del blocco</span>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={settings.enableMFA}
              onChange={(e) => handleInputChange('enableMFA', e.target.checked)}
            />
            <span>Abilita Autenticazione a Due Fattori (MFA)</span>
          </label>
          <span className="form-hint">Richiede un codice aggiuntivo per il login</span>
        </div>
      </div>
    </div>
  );

  const renderMonitoringSettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Monitoraggio</h2>
      <p className="section-description">Configura le impostazioni di monitoraggio e analisi</p>

      <div className="settings-grid">
        <div className="form-group">
          <label htmlFor="scanInterval">Intervallo Scansione (secondi)</label>
          <input
            id="scanInterval"
            type="number"
            className="input"
            min="30"
            max="600"
            step="30"
            value={settings.scanInterval}
            onChange={(e) => handleInputChange('scanInterval', parseInt(e.target.value))}
          />
          <span className="form-hint">Frequenza di scansione del traffico di rete</span>
        </div>

        <div className="form-group">
          <label htmlFor="logRetention">Conservazione Log (giorni)</label>
          <input
            id="logRetention"
            type="number"
            className="input"
            min="7"
            max="365"
            value={settings.logRetention}
            onChange={(e) => handleInputChange('logRetention', parseInt(e.target.value))}
          />
          <span className="form-hint">Tempo di conservazione dei log di sistema</span>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={settings.enableAutoBlock}
              onChange={(e) => handleInputChange('enableAutoBlock', e.target.checked)}
            />
            <span>Blocco Automatico Minacce</span>
          </label>
          <span className="form-hint">Blocca automaticamente gli IP identificati come minaccia</span>
        </div>

        <div className="form-group">
          <label htmlFor="threatThreshold">Soglia Minaccia: {settings.threatThreshold}/10</label>
          <input
            id="threatThreshold"
            type="range"
            min="1"
            max="10"
            step="1"
            value={settings.threatThreshold}
            onChange={(e) => handleInputChange('threatThreshold', parseInt(e.target.value))}
            className="slider"
          />
          <div className="slider-labels">
            <span>1 (Bassa)</span>
            <span>10 (Alta)</span>
          </div>
          <span className="form-hint">Livello minimo per considerare un evento come minaccia</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="settings-page">
      <div className="settings-header">
        <div className="header-content">
          <h1>Impostazioni</h1>
          <p>Configura e personalizza il tuo sistema FireDog</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-ghost" onClick={handleReset}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
            Ripristina Default
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <>
                <div className="spinner" />
                Salvataggio...
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                  <polyline points="17 21 17 13 7 13 7 21" />
                  <polyline points="7 3 7 8 15 8" />
                </svg>
                Salva Modifiche
              </>
            )}
          </button>
        </div>
      </div>

      {saveMessage && (
        <div className={`save-message ${saveMessage.type}`}>
          {saveMessage.type === 'success' ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          )}
          {saveMessage.text}
        </div>
      )}

      <div className="settings-tabs">
        <button
          className={`tab ${activeTab === 'general' ? 'active' : ''}`}
          onClick={() => setActiveTab('general')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v6m0 6v6" />
          </svg>
          Generali
        </button>
        <button
          className={`tab ${activeTab === 'appearance' ? 'active' : ''}`}
          onClick={() => setActiveTab('appearance')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
          </svg>
          Aspetto
        </button>
        <button
          className={`tab ${activeTab === 'notifications' ? 'active' : ''}`}
          onClick={() => setActiveTab('notifications')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          Notifiche
        </button>
        <button
          className={`tab ${activeTab === 'security' ? 'active' : ''}`}
          onClick={() => setActiveTab('security')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          Sicurezza
        </button>
        <button
          className={`tab ${activeTab === 'monitoring' ? 'active' : ''}`}
          onClick={() => setActiveTab('monitoring')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          Monitoraggio
        </button>
      </div>

      <div className="settings-content">
        {activeTab === 'general' && renderGeneralSettings()}
        {activeTab === 'appearance' && renderAppearanceSettings()}
        {activeTab === 'notifications' && renderNotificationSettings()}
        {activeTab === 'security' && renderSecuritySettings()}
        {activeTab === 'monitoring' && renderMonitoringSettings()}
      </div>
    </div>
  );
};

export default Settings;
