/**
 * Settings Page - System Configuration
 * Enhanced with SSH Keys Management and Database Management
 */
import React, { useState, useEffect } from 'react';
import './Settings.css';
import api from '../services/api';
import { useNotifications } from '../contexts/NotificationContext';
import NotificationsTab from '../components/Settings/NotificationsTab';
import SecurityTab from '../components/Settings/SecurityTab';

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

interface SSHKey {
  id: number;
  name: string;
  key_type: string;
  fingerprint: string;
  public_key: string;
  created_at: string;
  associated_targets: number;
  scope: 'global' | 'group' | 'target';
  scope_value?: string;
}

interface Target {
  id: number;
  hostname: string;
  ip_address: string;
  status: string;
  gruppo?: string | null;
  firedog_version?: string;
  last_seen?: string | null;
}

interface DBStats {
  total_size: string;
  targets_count: number;
  rules_count: number;
  threats_count: number;
  audit_logs_count: number;
  connection_status: 'connected' | 'error';
}

type TabType = 'general' | 'appearance' | 'notifications' | 'security' | 'monitoring' | 'ssh' | 'database';

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('general');
  const { showToast } = useNotifications();
  
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

  // SSH Keys State
  const [sshKeys, setSSHKeys] = useState<SSHKey[]>([]);
  const [loadingSSH, setLoadingSSH] = useState(false);
  const [showSSHModal, setShowSSHModal] = useState(false);
  const [sshKeyToDelete, setSSHKeyToDelete] = useState<number | null>(null);

  // Database State
  const [dbStats, setDBStats] = useState<DBStats | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loadingDB, setLoadingDB] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTargets, setSelectedTargets] = useState<number[]>([]);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

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

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  // Load data when switching tabs
  useEffect(() => {
    if (activeTab === 'ssh') {
      loadSSHKeys();
    } else if (activeTab === 'database') {
      loadDBData();
    }
  }, [activeTab]);

  // Apply CSS variables
  useEffect(() => {
    document.documentElement.style.setProperty('--font-primary', `'${settings.fontFamily}', sans-serif`);
    document.documentElement.style.setProperty('--font-base', `${settings.fontSize}px`);
    document.documentElement.style.setProperty('--radius-lg', `${settings.borderRadius}px`);
  }, [settings.fontFamily, settings.fontSize, settings.borderRadius]);

  // ============================================================================
  // SETTINGS CRUD
  // ============================================================================

  const loadSettings = async () => {
    try {
      // TODO: Replace with actual API call
      // const response = await api.get('/settings/');
      // setSettings(response.data);
      
      // For now, load from localStorage
      const savedSettings = localStorage.getItem('firedog_settings');
      if (savedSettings) {
        setSettings(JSON.parse(savedSettings));
      }
    } catch (error) {
      console.error('Error loading settings:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore caricamento impostazioni' });
    }
  };

  const handleInputChange = (field: keyof SettingsData, value: any) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);

    try {
      // TODO: Replace with actual API call
      // await api.post('/settings/', settings);
      
      // For now, save to localStorage
      localStorage.setItem('firedog_settings', JSON.stringify(settings));
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setSaveMessage({ type: 'success', text: 'Impostazioni salvate con successo!' });
      showToast({ type: 'success', title: 'Successo', message: 'Impostazioni salvate' });
    } catch (error) {
      setSaveMessage({ type: 'error', text: 'Errore nel salvataggio delle impostazioni.' });
      showToast({ type: 'error', title: 'Errore', message: 'Errore salvataggio impostazioni' });
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

  // ============================================================================
  // SSH KEYS MANAGEMENT
  // ============================================================================

  const loadSSHKeys = async () => {
    setLoadingSSH(true);
    try {
      // TODO: Replace with actual API call
      // const response = await api.get('/settings/ssh-keys/');
      // setSSHKeys(response.data);
      
      // Mock data for now
      setSSHKeys([
        {
          id: 1,
          name: 'Global Key',
          key_type: 'ed25519',
          fingerprint: 'SHA256:abc123...',
          public_key: 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...',
          created_at: '2024-01-15T10:30:00Z',
          associated_targets: 12,
          scope: 'global',
        },
        {
          id: 2,
          name: 'Production Group Key',
          key_type: 'ed25519',
          fingerprint: 'SHA256:def456...',
          public_key: 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...',
          created_at: '2024-02-20T14:20:00Z',
          associated_targets: 5,
          scope: 'group',
          scope_value: 'production',
        },
      ]);
    } catch (error) {
      console.error('Error loading SSH keys:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore caricamento chiavi SSH' });
    } finally {
      setLoadingSSH(false);
    }
  };

  const handleGenerateSSHKey = async (keyData: any) => {
    try {
      // TODO: Replace with actual API call
      // await api.post('/settings/ssh-keys/generate/', keyData);
      
      showToast({ type: 'success', title: 'Successo', message: 'Chiave SSH generata con successo' });
      loadSSHKeys();
      setShowSSHModal(false);
    } catch (error) {
      console.error('Error generating SSH key:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore generazione chiave SSH' });
    }
  };

  const handleDeleteSSHKey = async (keyId: number) => {
    try {
      // TODO: Replace with actual API call
      // await api.delete(`/settings/ssh-keys/${keyId}/`);
      
      showToast({ type: 'success', title: 'Successo', message: 'Chiave SSH eliminata' });
      loadSSHKeys();
      setSSHKeyToDelete(null);
    } catch (error) {
      console.error('Error deleting SSH key:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore eliminazione chiave SSH' });
    }
  };

  const handleDownloadPublicKey = (key: SSHKey) => {
    const blob = new Blob([key.public_key], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${key.name.replace(/\s+/g, '_')}_public.pub`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast({ type: 'success', title: 'Successo', message: 'Chiave pubblica scaricata' });
  };

  // ============================================================================
  // DATABASE MANAGEMENT
  // ============================================================================

  const loadDBData = async () => {
    setLoadingDB(true);
    try {
      // TODO: Replace with actual API calls
      // const [statsRes, targetsRes] = await Promise.all([
      //   api.get('/settings/database/stats/'),
      //   api.get('/targets/')
      // ]);
      // setDBStats(statsRes.data);
      // setTargets(targetsRes.data.results);
      
      // Mock data for now
      setDBStats({
        total_size: '245.8 MB',
        targets_count: 12,
        rules_count: 156,
        threats_count: 2341,
        audit_logs_count: 8923,
        connection_status: 'connected',
      });

      const targetsRes = await api.getTargets();
      setTargets(targetsRes.results || []);
    } catch (error) {
      console.error('Error loading DB data:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore caricamento dati database' });
    } finally {
      setLoadingDB(false);
    }
  };

  const handleTestDBConnection = async () => {
    try {
      // TODO: Replace with actual API call
      // await api.post('/settings/database/test-connection/');
      
      showToast({ type: 'success', title: 'Successo', message: 'Connessione database OK' });
    } catch (error) {
      showToast({ type: 'error', title: 'Errore', message: 'Errore connessione database' });
    }
  };

  const handleCleanupOldData = async () => {
    if (!window.confirm('Eliminare i dati vecchi? Questa operazione non può essere annullata.')) {
      return;
    }

    try {
      // TODO: Replace with actual API call
      // await api.post('/settings/database/cleanup/', {
      //   audit_logs_days: 90,
      //   threats_days: 180,
      //   statistics_days: 365,
      // });
      
      showToast({ type: 'success', title: 'Successo', message: 'Pulizia dati completata' });
      loadDBData();
    } catch (error) {
      showToast({ type: 'error', title: 'Errore', message: 'Errore pulizia dati' });
    }
  };

  const handleDeleteTargets = async () => {
    if (selectedTargets.length === 0) return;

    try {
      await Promise.all(
        selectedTargets.map(id => api.deleteTarget(id))
      );
      
      showToast({ type: 'success', title: 'Successo', message: `${selectedTargets.length} target eliminati` });
      setSelectedTargets([]);
      setShowDeleteModal(false);
      loadDBData();
    } catch (error) {
      console.error('Error deleting targets:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore eliminazione target' });
    }
  };

  const toggleTargetSelection = (targetId: number) => {
    setSelectedTargets(prev =>
      prev.includes(targetId)
        ? prev.filter(id => id !== targetId)
        : [...prev, targetId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedTargets.length === filteredTargets.length) {
      setSelectedTargets([]);
    } else {
      setSelectedTargets(filteredTargets.map(t => t.id));
    }
  };

  const filteredTargets = targets.filter(target =>
    target.hostname.toLowerCase().includes(searchTerm.toLowerCase()) ||
    target.ip_address.includes(searchTerm) ||
    target.gruppo?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // ============================================================================
  // RENDER FUNCTIONS FOR EACH TAB
  // ============================================================================

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
            <span>0px</span>
            <span>16px</span>
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
          <span className="form-hint">Attiva transizioni e animazioni nell'interfaccia</span>
        </div>
      </div>
    </div>
  );

  const renderNotificationSettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Notifiche</h2>
      <p className="section-description">Configura le notifiche del sistema</p>

      <div className="settings-grid">
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={settings.emailNotifications}
              onChange={(e) => handleInputChange('emailNotifications', e.target.checked)}
            />
            <span>Notifiche Email</span>
          </label>
          <span className="form-hint">Ricevi alert via email</span>
        </div>

        {settings.emailNotifications && (
          <div className="form-group">
            <label htmlFor="notificationEmail">Email per Notifiche</label>
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

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={settings.slackNotifications}
              onChange={(e) => handleInputChange('slackNotifications', e.target.checked)}
            />
            <span>Notifiche Slack</span>
          </label>
          <span className="form-hint">Invia alert a Slack</span>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={settings.discordNotifications}
              onChange={(e) => handleInputChange('discordNotifications', e.target.checked)}
            />
            <span>Notifiche Discord</span>
          </label>
          <span className="form-hint">Invia alert a Discord</span>
        </div>

        {(settings.slackNotifications || settings.discordNotifications) && (
          <div className="form-group">
            <label htmlFor="notificationWebhook">Webhook URL</label>
            <input
              id="notificationWebhook"
              type="url"
              className="input"
              placeholder="https://hooks.slack.com/..."
              value={settings.notificationWebhook}
              onChange={(e) => handleInputChange('notificationWebhook', e.target.value)}
            />
          </div>
        )}
      </div>
    </div>
  );

  const renderSecuritySettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Sicurezza</h2>
      <p className="section-description">Configura le impostazioni di sicurezza</p>

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

  const renderSSHSettings = () => (
    <div className="settings-section">
      <div className="section-header-with-action">
        <div>
          <h2 className="section-title">Chiavi SSH</h2>
          <p className="section-description">Gestisci le chiavi SSH per la connessione ai target</p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => setShowSSHModal(true)}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Genera Nuova Chiave
        </button>
      </div>

      {loadingSSH ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>Caricamento chiavi SSH...</p>
        </div>
      ) : sshKeys.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <h3>Nessuna chiave SSH configurata</h3>
          <p>Genera una nuova chiave per iniziare a connettere i target</p>
        </div>
      ) : (
        <div className="ssh-keys-list">
          {sshKeys.map(key => (
            <div key={key.id} className="ssh-key-card">
              <div className="ssh-key-header">
                <div className="ssh-key-info">
                  <h3>{key.name}</h3>
                  <div className="ssh-key-meta">
                    <span className="badge badge-info">{key.key_type.toUpperCase()}</span>
                    <span className="badge badge-secondary">
                      {key.scope === 'global' ? 'Globale' : 
                       key.scope === 'group' ? `Gruppo: ${key.scope_value}` :
                       `Target: ${key.scope_value}`}
                    </span>
                    <span className="ssh-key-targets">
                      {key.associated_targets} target associati
                    </span>
                  </div>
                </div>
                <div className="ssh-key-actions">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleDownloadPublicKey(key)}
                    title="Scarica chiave pubblica"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                  </button>
                  <button
                    className="btn btn-ghost btn-sm btn-danger"
                    onClick={() => setSSHKeyToDelete(key.id)}
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
                <div className="ssh-key-fingerprint">
                  <label>Fingerprint:</label>
                  <code>{key.fingerprint}</code>
                </div>
                <div className="ssh-key-created">
                  <label>Creata:</label>
                  <span>{new Date(key.created_at).toLocaleString('it-IT')}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderDatabaseSettings = () => (
    <div className="settings-section">
      <h2 className="section-title">Gestione Database</h2>
      <p className="section-description">Gestisci il database e i target registrati</p>

      {/* Database Stats */}
      <div className="db-stats-grid">
        <div className="stat-card">
          <div className="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <ellipse cx="12" cy="5" rx="9" ry="3" />
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Dimensione DB</div>
            <div className="stat-value">{dbStats?.total_size || '---'}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Target</div>
            <div className="stat-value">{dbStats?.targets_count || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Minacce</div>
            <div className="stat-value">{dbStats?.threats_count || 0}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <div className="stat-content">
            <div className="stat-label">Audit Log</div>
            <div className="stat-value">{dbStats?.audit_logs_count || 0}</div>
          </div>
        </div>
      </div>

      {/* Database Actions */}
      <div className="db-actions">
        <button 
          className="btn btn-secondary"
          onClick={handleTestDBConnection}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          Test Connessione
        </button>

        <button 
          className="btn btn-secondary"
          onClick={handleCleanupOldData}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            <line x1="10" y1="11" x2="10" y2="17" />
            <line x1="14" y1="11" x2="14" y2="17" />
          </svg>
          Pulizia Dati Vecchi
        </button>
      </div>

      {/* Target Management */}
      <div className="target-management">
        <div className="target-management-header">
          <h3>Gestione Target</h3>
          <div className="target-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Cerca per IP, hostname o gruppo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input"
            />
          </div>
        </div>

        {filteredTargets.length > 0 && (
          <div className="target-bulk-actions">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={selectedTargets.length === filteredTargets.length}
                onChange={toggleSelectAll}
              />
              <span>Seleziona tutti ({filteredTargets.length})</span>
            </label>
            {selectedTargets.length > 0 && (
              <button
                className="btn btn-danger btn-sm"
                onClick={() => setShowDeleteModal(true)}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                </svg>
                Elimina Selezionati ({selectedTargets.length})
              </button>
            )}
          </div>
        )}

        {loadingDB ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Caricamento target...</p>
          </div>
        ) : filteredTargets.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
              <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
            </svg>
            <h3>Nessun target trovato</h3>
            <p>Nessun target corrisponde ai criteri di ricerca</p>
          </div>
        ) : (
          <div className="targets-table">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '40px' }}></th>
                  <th>Hostname</th>
                  <th>IP Address</th>
                  <th>Gruppo</th>
                  <th>Status</th>
                  <th>Versione</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filteredTargets.map(target => (
                  <tr key={target.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedTargets.includes(target.id)}
                        onChange={() => toggleTargetSelection(target.id)}
                      />
                    </td>
                    <td>{target.hostname}</td>
                    <td><code>{target.ip_address}</code></td>
                    <td>
                      {target.gruppo && (
                        <span className="badge badge-secondary">{target.gruppo}</span>
                      )}
                    </td>
                    <td>
                      <span className={`status-badge status-${target.status}`}>
                        {target.status}
                      </span>
                    </td>
                    <td>{target.firedog_version || '---'}</td>
                    <td>
                      <button
                        className="btn btn-ghost btn-sm btn-danger"
                        onClick={() => {
                          setSelectedTargets([target.id]);
                          setShowDeleteModal(true);
                        }}
                        title="Elimina target"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );

  // ============================================================================
  // MAIN RENDER
  // ============================================================================

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
        <button
          className={`tab ${activeTab === 'ssh' ? 'active' : ''}`}
          onClick={() => setActiveTab('ssh')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          Chiavi SSH
        </button>
        <button
          className={`tab ${activeTab === 'database' ? 'active' : ''}`}
          onClick={() => setActiveTab('database')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          Database
        </button>
      </div>

      <div className="settings-content">
        {activeTab === 'general' && renderGeneralSettings()}
        {activeTab === 'appearance' && renderAppearanceSettings()}
        {activeTab === 'notifications' && <NotificationsTab />}
        {activeTab === 'security' && <SecurityTab />}
        {activeTab === 'monitoring' && renderMonitoringSettings()}
        {activeTab === 'ssh' && renderSSHSettings()}
        {activeTab === 'database' && renderDatabaseSettings()}
      </div>

      {/* SSH Key Generation Modal */}
      {showSSHModal && (
        <SSHKeyModal
          onClose={() => setShowSSHModal(false)}
          onGenerate={handleGenerateSSHKey}
        />
      )}

      {/* SSH Key Delete Confirmation */}
      {sshKeyToDelete !== null && (
        <ConfirmModal
          title="Elimina Chiave SSH"
          message="Sei sicuro di voler eliminare questa chiave SSH? I target che la utilizzano non saranno più accessibili."
          confirmText="Elimina"
          onConfirm={() => handleDeleteSSHKey(sshKeyToDelete)}
          onCancel={() => setSSHKeyToDelete(null)}
          variant="danger"
        />
      )}

      {/* Target Delete Confirmation */}
      {showDeleteModal && (
        <ConfirmModal
          title="Elimina Target"
          message={`Sei sicuro di voler eliminare ${selectedTargets.length} target dal database? Questa operazione non può essere annullata.`}
          confirmText="Elimina"
          onConfirm={handleDeleteTargets}
          onCancel={() => {
            setShowDeleteModal(false);
            setSelectedTargets([]);
          }}
          variant="danger"
        />
      )}
    </div>
  );
};

// ============================================================================
// MODALS COMPONENTS
// ============================================================================

interface SSHKeyModalProps {
  onClose: () => void;
  onGenerate: (data: any) => void;
}

const SSHKeyModal: React.FC<SSHKeyModalProps> = ({ onClose, onGenerate }) => {
  const [formData, setFormData] = useState({
    name: '',
    key_type: 'ed25519',
    key_size: '4096',
    scope: 'global',
    scope_value: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate(formData);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Genera Nuova Chiave SSH</h2>
          <button className="modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label htmlFor="keyName">Nome Chiave</label>
              <input
                id="keyName"
                type="text"
                className="input"
                placeholder="es: Production Key"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="keyType">Tipo Chiave</label>
              <select
                id="keyType"
                className="input"
                value={formData.key_type}
                onChange={(e) => setFormData({ ...formData, key_type: e.target.value })}
              >
                <option value="ed25519">Ed25519 (Consigliato)</option>
                <option value="rsa">RSA</option>
                <option value="ecdsa">ECDSA</option>
              </select>
              <span className="form-hint">Ed25519 è più sicuro e veloce</span>
            </div>

            {formData.key_type === 'rsa' && (
              <div className="form-group">
                <label htmlFor="keySize">Dimensione Chiave</label>
                <select
                  id="keySize"
                  className="input"
                  value={formData.key_size}
                  onChange={(e) => setFormData({ ...formData, key_size: e.target.value })}
                >
                  <option value="2048">2048 bit</option>
                  <option value="3072">3072 bit</option>
                  <option value="4096">4096 bit (Consigliato)</option>
                </select>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="scope">Ambito</label>
              <select
                id="scope"
                className="input"
                value={formData.scope}
                onChange={(e) => setFormData({ ...formData, scope: e.target.value, scope_value: '' })}
              >
                <option value="global">Globale (tutti i target)</option>
                <option value="group">Gruppo specifico</option>
                <option value="target">Target specifico</option>
              </select>
            </div>

            {formData.scope !== 'global' && (
              <div className="form-group">
                <label htmlFor="scopeValue">
                  {formData.scope === 'group' ? 'Nome Gruppo' : 'ID Target'}
                </label>
                <input
                  id="scopeValue"
                  type="text"
                  className="input"
                  placeholder={formData.scope === 'group' ? 'es: production' : 'es: 1'}
                  value={formData.scope_value}
                  onChange={(e) => setFormData({ ...formData, scope_value: e.target.value })}
                  required
                />
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Annulla
            </button>
            <button type="submit" className="btn btn-primary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Genera Chiave
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface ConfirmModalProps {
  title: string;
  message: string;
  confirmText: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'danger' | 'warning' | 'info';
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
  title,
  message,
  confirmText,
  onConfirm,
  onCancel,
  variant = 'danger',
}) => {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content modal-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onCancel}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="modal-body">
          <p>{message}</p>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel}>
            Annulla
          </button>
          <button 
            className={`btn btn-${variant}`} 
            onClick={() => {
              onConfirm();
              onCancel();
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
