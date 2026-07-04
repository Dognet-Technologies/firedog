/**
 * Settings Page - System Configuration
 * Enhanced with SSH Keys Management and Database Management
 */
import React, { useState, useEffect } from 'react';
import './Settings.css';
import api from '../services/api';
import MCPKeysTab from '../components/Settings/MCPKeysTab';
import { useNotifications } from '../contexts/NotificationContext';
import { useAuth } from '../contexts/AuthContext';
import type { NotificationConfig, SmtpInfo } from '../types';

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

interface AgentAPIKey {
  id: number;
  key_hash: string;
  is_active: boolean;
  created_at: string;
  expires_at?: string;
  created_by?: number;
  created_by_username?: string;
  last_used_at?: string;
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

interface UserProfile {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login: string;
}

type TabType = 'general' | 'appearance' | 'notifications' | 'security' | 'monitoring' | 'ssh' | 'database' | 'mcp';

interface UpdateCheckResponse {
  ok: boolean;
  error?: string;
  branch?: string;
  installed?: string;
  available?: string;
  commits_behind?: number;
  changelog?: string[];
  up_to_date?: boolean;
}

interface UpdateInstallResponse {
  ok: boolean;
  exit_code?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

const UpdateSection: React.FC = () => {
  const { showToast, showConfirm } = useNotifications();
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [info, setInfo] = useState<UpdateCheckResponse | null>(null);
  const [lastInstall, setLastInstall] = useState<UpdateInstallResponse | null>(null);

  const handleCheck = async () => {
    setChecking(true);
    try {
      const resp = await api.checkSystemUpdate();
      setInfo(resp);
      if (!resp.ok) {
        showToast({ type: 'error', title: 'Check fallito', message: resp.error || 'Errore' });
      } else if (resp.up_to_date) {
        showToast({ type: 'success', title: 'Aggiornato', message: 'Versione più recente già installata' });
      } else {
        showToast({ type: 'info', title: 'Update disponibile', message: `${resp.commits_behind} commit indietro su ${resp.branch}` });
      }
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Errore di rete';
      showToast({ type: 'error', title: 'Check fallito', message: msg });
    } finally {
      setChecking(false);
    }
  };

  const handleInstall = async () => {
    showConfirm({
      title: 'Installa aggiornamento',
      message: 'Verrà eseguito git pull, rebuild del frontend, migrazioni DB e restart del backend/celery. Il sistema sarà brevemente offline. Procedere?',
      confirmText: 'Installa',
      cancelText: 'Annulla',
      type: 'warning',
      onConfirm: async () => {
        setInstalling(true);
        setLastInstall(null);
        try {
          const resp = await api.installSystemUpdate();
          setLastInstall(resp);
          if (resp.ok) {
            showToast({ type: 'success', title: 'Update completato', message: 'Backend riavviato. Ricarica la pagina.' });
            // re-check per refreshare versione installata
            handleCheck();
          } else {
            showToast({ type: 'error', title: 'Update fallito', message: resp.error || `exit ${resp.exit_code}` });
          }
        } catch (e: unknown) {
          const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Errore di rete';
          showToast({ type: 'error', title: 'Update fallito', message: msg });
        } finally {
          setInstalling(false);
        }
      },
    });
  };

  return (
    <div className="settings-update-section" style={{ marginTop: 24, paddingTop: 24, borderTop: '1px solid var(--border-color, #333)' }}>
      <h2 className="section-title">Aggiornamenti</h2>
      <p className="section-description">Scarica e installa l'ultima versione del codice dal repository GitHub.</p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <button className="btn-secondary" onClick={handleCheck} disabled={checking || installing}>
          {checking ? 'Checking…' : 'Verifica aggiornamenti'}
        </button>
        <button
          className="btn-primary"
          onClick={handleInstall}
          disabled={installing || checking || !info?.ok || info?.up_to_date}
          title={info?.up_to_date ? 'Già aggiornato' : 'Installa update'}
        >
          {installing ? 'Installazione in corso…' : 'Installa update'}
        </button>
      </div>

      {info && info.ok && (
        <div style={{ background: 'var(--bg-secondary, #1a1a1a)', padding: 12, borderRadius: 6, fontFamily: 'monospace', fontSize: 12 }}>
          <div>Branch:    <strong>{info.branch}</strong></div>
          <div>Installato: {info.installed}</div>
          <div>Disponibile: {info.available}</div>
          <div>Commits behind: <strong style={{ color: (info.commits_behind ?? 0) > 0 ? 'var(--status-warning)' : 'var(--status-success)' }}>{info.commits_behind ?? 0}</strong></div>
          {info.changelog && info.changelog.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: 'pointer' }}>Changelog ({info.changelog.length})</summary>
              <ul style={{ marginTop: 6 }}>
                {info.changelog.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}

      {info && !info.ok && (
        <div style={{ background: 'var(--bg-secondary, #2a1a1a)', padding: 12, borderRadius: 6, color: 'var(--status-danger)' }}>
          {info.error}
        </div>
      )}

      {lastInstall && (
        <details style={{ marginTop: 12 }}>
          <summary style={{ cursor: 'pointer' }}>Log esecuzione update.sh (exit {lastInstall.exit_code})</summary>
          <pre style={{ background: 'var(--bg-secondary, #1a1a1a)', padding: 12, borderRadius: 6, maxHeight: 400, overflow: 'auto', fontSize: 11 }}>
            {lastInstall.stdout || ''}
            {lastInstall.stderr ? `\n--- STDERR ---\n${lastInstall.stderr}` : ''}
          </pre>
        </details>
      )}
    </div>
  );
};

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('general');
  const { showToast, showConfirm } = useNotifications();
  const { user } = useAuth();
  
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

  // Agent API Keys State
  const [agentAPIKeys, setAgentAPIKeys] = useState<AgentAPIKey[]>([]);
  const [loadingAgentKeys, setLoadingAgentKeys] = useState(false);
  const [showAgentKeyModal, setShowAgentKeyModal] = useState(false);
  const [agentKeyToDelete, setAgentKeyToDelete] = useState<number | null>(null);
  const [generatedAPIKey, setGeneratedAPIKey] = useState<string | null>(null);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForRetrieve, setPasswordForRetrieve] = useState('');
  const [keyIdToRetrieve, setKeyIdToRetrieve] = useState<number | null>(null);
  const [retrievedKey, setRetrievedKey] = useState<string | null>(null);
  const [retrievingKey, setRetrievingKey] = useState(false);

  // Database State
  const [dbStats, setDBStats] = useState<DBStats | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loadingDB, setLoadingDB] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTargets, setSelectedTargets] = useState<number[]>([]);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Notifications State
  const [notificationConfig, setNotificationConfig] = useState<NotificationConfig | null>(null);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const [savingNotifications, setSavingNotifications] = useState(false);
  const [testingNotification, setTestingNotification] = useState<string | null>(null);
  const [showSmtpInfo, setShowSmtpInfo] = useState(false);
  const [smtpInfo, setSmtpInfo] = useState<SmtpInfo | null>(null);
  const [notificationFormData, setNotificationFormData] = useState<Partial<NotificationConfig>>({
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

  // Security State
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loadingSecurity, setLoadingSecurity] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [changingUsername, setChangingUsername] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [changingPassword, setChangingPassword] = useState(false);
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  });
  const [passwordStrength, setPasswordStrength] = useState({
    score: 0,
    label: '',
    color: ''
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

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  // Load data when switching tabs
  useEffect(() => {
    if (activeTab === 'ssh') {
      loadAgentAPIKeys();
    } else if (activeTab === 'database') {
      loadDBData();
    } else if (activeTab === 'notifications') {
      loadNotificationConfig();
    } else if (activeTab === 'security') {
      loadUserProfile();
    }
  }, [activeTab]);

  // Password strength checker
  useEffect(() => {
    if (passwordForm.new_password) {
      checkPasswordStrength(passwordForm.new_password);
    } else {
      setPasswordStrength({ score: 0, label: '', color: '' });
    }
  }, [passwordForm.new_password]);

  // Apply CSS variables
  useEffect(() => {
    const r = settings.fontSize / 14;
    document.documentElement.style.setProperty('--font-primary', `'${settings.fontFamily}', sans-serif`);
    document.documentElement.style.setProperty('--font-xs',   `${Math.round(11 * r)}px`);
    document.documentElement.style.setProperty('--font-sm',   `${Math.round(13 * r)}px`);
    document.documentElement.style.setProperty('--font-base', `${settings.fontSize}px`);
    document.documentElement.style.setProperty('--font-md',   `${Math.round(16 * r)}px`);
    document.documentElement.style.setProperty('--font-lg',   `${Math.round(18 * r)}px`);
    document.documentElement.style.setProperty('--font-xl',   `${Math.round(20 * r)}px`);
    document.documentElement.style.setProperty('--font-2xl',  `${Math.round(24 * r)}px`);
    document.documentElement.style.setProperty('--font-3xl',  `${Math.round(30 * r)}px`);
    document.documentElement.style.setProperty('--font-4xl',  `${Math.round(36 * r)}px`);
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
  // AGENT API KEYS MANAGEMENT
  // ============================================================================

  const loadAgentAPIKeys = async () => {
    setLoadingAgentKeys(true);
    try {
      const keys = await api.getAgentAPIKeys();
      setAgentAPIKeys(keys);
    } catch (error) {
      console.error('Error loading Agent API keys:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore caricamento API Keys' });
    } finally {
      setLoadingAgentKeys(false);
    }
  };

  const handleGenerateAgentAPIKey = async () => {
    try {
      const response = await api.generateAgentAPIKey();
      setGeneratedAPIKey(response.raw_key);
      showToast({ type: 'success', title: 'Successo', message: 'API Key generata con successo' });
      loadAgentAPIKeys();
      setShowAgentKeyModal(true);
    } catch (error) {
      console.error('Error generating Agent API key:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore generazione API Key' });
    }
  };

  const handleDeleteAgentAPIKey = async (keyId: number) => {
    try {
      await api.deleteAgentAPIKey(keyId);
      showToast({ type: 'success', title: 'Successo', message: 'API Key eliminata' });
      loadAgentAPIKeys();
      setAgentKeyToDelete(null);
    } catch (error) {
      console.error('Error deleting Agent API key:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore eliminazione API Key' });
    }
  };

  const handleToggleAgentAPIKey = async (keyId: number, isActive: boolean) => {
    try {
      if (isActive) {
        await api.deactivateAgentAPIKey(keyId);
        showToast({ type: 'success', title: 'Successo', message: 'API Key disattivata' });
      } else {
        await api.activateAgentAPIKey(keyId);
        showToast({ type: 'success', title: 'Successo', message: 'API Key attivata' });
      }
      loadAgentAPIKeys();
    } catch (error) {
      console.error('Error toggling Agent API key:', error);
      showToast({ type: 'error', title: 'Errore', message: 'Errore modifica stato API Key' });
    }
  };

  const handleCloseGeneratedKeyModal = () => {
    setShowAgentKeyModal(false);
    setGeneratedAPIKey(null);
  };

  const handleShowKeyRequest = (keyId: number) => {
    setKeyIdToRetrieve(keyId);
    setShowPasswordModal(true);
    setPasswordForRetrieve('');
    setRetrievedKey(null);
  };

  const handleRetrieveKey = async () => {
    if (!keyIdToRetrieve || !passwordForRetrieve) {
      showToast({ type: 'error', title: 'Errore', message: 'Inserisci la password' });
      return;
    }

    setRetrievingKey(true);
    try {
      const response = await api.retrieveAgentAPIKey(keyIdToRetrieve, passwordForRetrieve);
      setRetrievedKey(response.raw_key);
      showToast({ type: 'success', title: 'Successo', message: 'API Key recuperata' });
    } catch (error: any) {
      console.error('Error retrieving API key:', error);
      if (error.response?.status === 401) {
        showToast({ type: 'error', title: 'Errore', message: 'Password non valida' });
      } else if (error.response?.status === 404) {
        showToast({ type: 'error', title: 'Errore', message: 'Questa chiave è stata creata prima della funzionalità di recupero. Genera una nuova chiave.' });
      } else {
        showToast({ type: 'error', title: 'Errore', message: 'Errore recupero API Key' });
      }
    } finally {
      setRetrievingKey(false);
    }
  };

  const handleClosePasswordModal = () => {
    setShowPasswordModal(false);
    setPasswordForRetrieve('');
    setKeyIdToRetrieve(null);
    setRetrievedKey(null);
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
  // NOTIFICATIONS MANAGEMENT
  // ============================================================================

  const loadNotificationConfig = async () => {
    try {
      setLoadingNotifications(true);
      const data = await api.getNotificationConfig();
      setNotificationConfig(data);
      setNotificationFormData(data);
    } catch (error: any) {
      console.error('Error loading notification config:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare configurazione notifiche'
      });
    } finally {
      setLoadingNotifications(false);
    }
  };

  const handleSaveNotifications = async () => {
    try {
      setSavingNotifications(true);

      // Validazione
      if (notificationFormData.email_enabled) {
        if (!notificationFormData.email_recipients || notificationFormData.email_recipients.length === 0) {
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Inserisci almeno un indirizzo email'
          });
          return;
        }

        if (!notificationFormData.smtp_host || !notificationFormData.smtp_user) {
          showToast({
            type: 'error',
            title: 'Errore',
            message: 'Configurazione SMTP incompleta'
          });
          return;
        }
      }

      if (notificationFormData.slack_enabled && !notificationFormData.slack_webhook_url) {
        showToast({
          type: 'error',
          title: 'Errore',
          message: 'Inserisci webhook URL Slack'
        });
        return;
      }

      if (notificationFormData.discord_enabled && !notificationFormData.discord_webhook_url) {
        showToast({
          type: 'error',
          title: 'Errore',
          message: 'Inserisci webhook URL Discord'
        });
        return;
      }

      const updated = await api.updateNotificationConfig(notificationFormData);
      setNotificationConfig(updated);
      setNotificationFormData(updated);

      showToast({
        type: 'success',
        title: 'Successo',
        message: 'Configurazione notifiche salvata'
      });
    } catch (error: any) {
      console.error('Error saving notification config:', error);
      showToast({
        type: 'error',
        title: 'Errore',
        message: error.response?.data?.message || 'Errore salvataggio configurazione'
      });
    } finally {
      setSavingNotifications(false);
    }
  };

  const handleTestNotification = async (type: 'email' | 'slack' | 'discord') => {
    try {
      setTestingNotification(type);

      const data: any = { notification_type: type };

      if (type === 'email' && testRecipient) {
        data.test_recipient = testRecipient;
      }

      const result = await api.testNotification(data);

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
      setTestingNotification(null);
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

    const recipients = notificationFormData.email_recipients || [];

    if (recipients.includes(emailInput)) {
      showToast({
        type: 'warning',
        title: 'Attenzione',
        message: 'Email già presente'
      });
      return;
    }

    setNotificationFormData({
      ...notificationFormData,
      email_recipients: [...recipients, emailInput]
    });

    setEmailInput('');
  };

  const removeEmailRecipient = (email: string) => {
    setNotificationFormData({
      ...notificationFormData,
      email_recipients: (notificationFormData.email_recipients || []).filter(e => e !== email)
    });
  };

  const loadSmtpInfo = async () => {
    try {
      const data = await api.getSmtpInfo();
      setSmtpInfo(data);
      setShowSmtpInfo(true);
    } catch (error) {
      console.error('Error loading SMTP info:', error);
    }
  };

  // ============================================================================
  // SECURITY / USER PROFILE MANAGEMENT
  // ============================================================================

  const loadUserProfile = async () => {
    try {
      setLoadingSecurity(true);
      const data = await api.getUserProfile();
      setUserProfile(data);
      setNewUsername(data.username);
    } catch (error: any) {
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare profilo utente'
      });
    } finally {
      setLoadingSecurity(false);
    }
  };

  const checkPasswordStrength = (password: string) => {
    let score = 0;

    // Lunghezza
    if (password.length >= 9) score += 1;
    if (password.length >= 12) score += 1;

    // Maiuscole
    const uppercase = password.match(/[A-Z]/g);
    if (uppercase && uppercase.length >= 2) score += 1;

    // Minuscole
    const lowercase = password.match(/[a-z]/g);
    if (lowercase && lowercase.length >= 2) score += 1;

    // Numeri
    const numbers = password.match(/[0-9]/g);
    if (numbers && numbers.length >= 2) score += 1;

    // Caratteri speciali
    const special = password.match(/[^a-zA-Z0-9]/g);
    if (special && special.length >= 2) score += 1;

    // Determina label e colore
    let label = '';
    let color = '';

    if (score < 3) {
      label = 'Debole';
      color = '#ef4444'; // red
    } else if (score < 5) {
      label = 'Media';
      color = '#f59e0b'; // orange
    } else if (score < 6) {
      label = 'Buona';
      color = '#10b981'; // green
    } else {
      label = 'Eccellente';
      color = '#06b6d4'; // cyan
    }

    setPasswordStrength({ score, label, color });
  };

  const handleChangeUsername = async () => {
    if (!newUsername || newUsername === userProfile?.username) {
      return;
    }

    showConfirm({
      title: 'Conferma Cambio Username',
      message: `Vuoi cambiare il tuo username da "${userProfile?.username}" a "${newUsername}"?`,
      confirmText: 'Cambia Username',
      type: 'warning',
      onConfirm: async () => {
        try {
          setChangingUsername(true);
          await api.changeUsername(newUsername);

          showToast({
            type: 'success',
            title: 'Username Aggiornato',
            message: `Il tuo username è stato cambiato in "${newUsername}"`
          });

          // Ricarica profilo
          await loadUserProfile();
        } catch (error: any) {
          const errorMsg = error.response?.data?.new_username?.[0] ||
                          error.response?.data?.detail ||
                          'Errore durante il cambio username';

          showToast({
            type: 'error',
            title: 'Errore',
            message: errorMsg
          });

          // Ripristina username originale
          setNewUsername(userProfile?.username || '');
        } finally {
          setChangingUsername(false);
        }
      }
    });
  };

  const handleChangePassword = async () => {
    // Validazione form
    if (!passwordForm.current_password) {
      showToast({
        type: 'error',
        title: 'Campo obbligatorio',
        message: 'Inserisci la password attuale'
      });
      return;
    }

    if (!passwordForm.new_password) {
      showToast({
        type: 'error',
        title: 'Campo obbligatorio',
        message: 'Inserisci la nuova password'
      });
      return;
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      showToast({
        type: 'error',
        title: 'Password non corrispondono',
        message: 'La nuova password e la conferma non corrispondono'
      });
      return;
    }

    // Validazione requisiti password
    const validationErrors = validatePassword(passwordForm.new_password);
    if (validationErrors.length > 0) {
      showToast({
        type: 'error',
        title: 'Password non valida',
        message: validationErrors.join('\n')
      });
      return;
    }

    showConfirm({
      title: 'Conferma Cambio Password',
      message: 'Sei sicuro di voler cambiare la tua password?',
      confirmText: 'Cambia Password',
      type: 'warning',
      onConfirm: async () => {
        try {
          setChangingPassword(true);
          await api.changePassword(passwordForm);

          showToast({
            type: 'success',
            title: 'Password Aggiornata',
            message: 'La tua password è stata cambiata con successo'
          });

          // Reset form
          setPasswordForm({
            current_password: '',
            new_password: '',
            confirm_password: ''
          });
        } catch (error: any) {
          const errorMsg = error.response?.data?.current_password?.[0] ||
                          error.response?.data?.new_password?.[0] ||
                          error.response?.data?.confirm_password?.[0] ||
                          error.response?.data?.detail ||
                          'Errore durante il cambio password';

          showToast({
            type: 'error',
            title: 'Errore',
            message: errorMsg
          });
        } finally {
          setChangingPassword(false);
        }
      }
    });
  };

  const validatePassword = (password: string): string[] => {
    const errors: string[] = [];

    if (password.length < 9) {
      errors.push('• Minimo 9 caratteri');
    }

    const uppercase = password.match(/[A-Z]/g);
    if (!uppercase || uppercase.length < 2) {
      errors.push('• Almeno 2 lettere maiuscole');
    }

    const lowercase = password.match(/[a-z]/g);
    if (!lowercase || lowercase.length < 2) {
      errors.push('• Almeno 2 lettere minuscole');
    }

    const numbers = password.match(/[0-9]/g);
    if (!numbers || numbers.length < 2) {
      errors.push('• Almeno 2 numeri');
    }

    const special = password.match(/[^a-zA-Z0-9]/g);
    if (!special || special.length < 2) {
      errors.push('• Almeno 2 caratteri speciali (!@#$%^&*...)');
    }

    return errors;
  };

  const togglePasswordVisibility = (field: 'current' | 'new' | 'confirm') => {
    setShowPasswords({
      ...showPasswords,
      [field]: !showPasswords[field]
    });
  };

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

      <UpdateSection />
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

  const renderNotificationSettings = () => {
    if (loadingNotifications) {
      return (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Caricamento configurazione...</p>
        </div>
      );
    }

    return (
      <>
        <div className="settings-section">
          <h2 className="section-title">Notifiche Email</h2>
          <p className="section-description">Configurazione notifiche tramite email</p>
          <div className="settings-grid">
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.email_enabled || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, email_enabled: e.target.checked })}
                />
                <span>Abilita notifiche email</span>
              </label>
            </div>

            {notificationFormData.email_enabled && (
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
                      className="input"
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
                    {(notificationFormData.email_recipients || []).map((email, index) => (
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

                <div className="form-group">
                  <label htmlFor="smtp-host">SMTP Host</label>
                  <input
                    id="smtp-host"
                    type="text"
                    value={notificationFormData.smtp_host || ''}
                    onChange={e => setNotificationFormData({ ...notificationFormData, smtp_host: e.target.value })}
                    placeholder="smtp.gmail.com"
                    className="input"
                  />
                  <span className="form-hint">
                    Server SMTP per l'invio delle email - <button className="btn-link" onClick={loadSmtpInfo}>Guida configurazione</button>
                  </span>
                </div>

                <div className="form-group">
                  <label htmlFor="smtp-port">SMTP Port</label>
                  <input
                    id="smtp-port"
                    type="number"
                    value={notificationFormData.smtp_port || 587}
                    onChange={e => setNotificationFormData({ ...notificationFormData, smtp_port: parseInt(e.target.value) })}
                    className="input"
                  />
                  <span className="form-hint">Porta del server SMTP (solitamente 587 o 465)</span>
                </div>

                <div className="form-group">
                  <label htmlFor="smtp-user">SMTP Username</label>
                  <input
                    id="smtp-user"
                    type="text"
                    value={notificationFormData.smtp_user || ''}
                    onChange={e => setNotificationFormData({ ...notificationFormData, smtp_user: e.target.value })}
                    placeholder="microcyber"
                    className="input"
                  />
                  <span className="form-hint">Username per l'autenticazione SMTP</span>
                </div>

                <div className="form-group">
                  <label htmlFor="smtp-password">SMTP Password</label>
                  <input
                    id="smtp-password"
                    type="password"
                    value={notificationFormData.smtp_password || ''}
                    onChange={e => setNotificationFormData({ ...notificationFormData, smtp_password: e.target.value })}
                    placeholder="••••••••"
                    className="input"
                  />
                  <span className="form-hint">Password per l'autenticazione SMTP</span>
                </div>

                <div className="form-group">
                  <label htmlFor="smtp-from">Email Mittente</label>
                  <input
                    id="smtp-from"
                    type="email"
                    value={notificationFormData.smtp_from_email || ''}
                    onChange={e => setNotificationFormData({ ...notificationFormData, smtp_from_email: e.target.value })}
                    placeholder="firedog@localhost"
                    className="input"
                  />
                  <span className="form-hint">Indirizzo email del mittente</span>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={notificationFormData.smtp_use_tls || false}
                      onChange={e => setNotificationFormData({ ...notificationFormData, smtp_use_tls: e.target.checked })}
                    />
                    <span>Usa TLS/STARTTLS</span>
                  </label>
                  <span className="form-hint">Abilita crittografia TLS per connessioni sicure</span>
                </div>

                <div className="form-group">
                  <label htmlFor="test-email">Test Email (opzionale)</label>
                  <input
                    id="test-email"
                    type="email"
                    value={testRecipient}
                    onChange={e => setTestRecipient(e.target.value)}
                    placeholder="test@example.com"
                    className="input"
                  />
                  <button
                    type="button"
                    onClick={() => handleTestNotification('email')}
                    disabled={testingNotification === 'email'}
                    className="btn-secondary"
                  >
                    {testingNotification === 'email' ? 'Invio...' : 'Invia Test Email'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="settings-section">
          <h2 className="section-title">Notifiche Slack</h2>
          <p className="section-description">Configurazione notifiche tramite Slack</p>
          <div className="settings-grid">
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.slack_enabled || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, slack_enabled: e.target.checked })}
                />
                <span>Abilita notifiche Slack</span>
              </label>
            </div>

            {notificationFormData.slack_enabled && (
              <>
                <div className="form-group">
                  <label htmlFor="slack-webhook">Webhook URL Slack</label>
                  <input
                    id="slack-webhook"
                    type="url"
                    value={notificationFormData.slack_webhook_url || ''}
                    onChange={e => setNotificationFormData({ ...notificationFormData, slack_webhook_url: e.target.value })}
                    placeholder="https://hooks.slack.com/services/..."
                    className="input"
                  />
                  <span className="form-hint">
                    Crea un webhook su: https://api.slack.com/messaging/webhooks
                  </span>
                </div>

                <div className="form-group">
                  <button
                    type="button"
                    onClick={() => handleTestNotification('slack')}
                    disabled={testingNotification === 'slack'}
                    className="btn-secondary"
                  >
                    {testingNotification === 'slack' ? 'Invio...' : 'Invia Test Slack'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="settings-section">
          <h2 className="section-title">Notifiche Discord</h2>
          <p className="section-description">Configurazione notifiche tramite Discord</p>
          <div className="settings-grid">
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.discord_enabled || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, discord_enabled: e.target.checked })}
                />
                <span>Abilita notifiche Discord</span>
              </label>
            </div>

            {notificationFormData.discord_enabled && (
              <>
                <div className="form-group">
                  <label htmlFor="discord-webhook">Webhook URL Discord</label>
                  <input
                    id="discord-webhook"
                    type="url"
                    value={notificationFormData.discord_webhook_url || ''}
                    onChange={e => setNotificationFormData({ ...notificationFormData, discord_webhook_url: e.target.value })}
                    placeholder="https://discord.com/api/webhooks/..."
                    className="input"
                  />
                  <span className="form-hint">
                    Server Settings → Integrations → Webhooks → New Webhook
                  </span>
                </div>

                <div className="form-group">
                  <button
                    type="button"
                    onClick={() => handleTestNotification('discord')}
                    disabled={testingNotification === 'discord'}
                    className="btn-secondary"
                  >
                    {testingNotification === 'discord' ? 'Invio...' : 'Invia Test Discord'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="settings-section">
          <h2 className="section-title">Trigger Notifiche</h2>
          <p className="section-description">
            Configura quando ricevere notifiche. Gli alert si basano sulla soglia minaccia configurata nelle impostazioni di monitoraggio.
          </p>

          <div className="settings-grid">
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.alert_on_critical_threat || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, alert_on_critical_threat: e.target.checked })}
                />
                <span>Minacce critiche</span>
              </label>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.alert_on_high_threat || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, alert_on_high_threat: e.target.checked })}
                />
                <span>Minacce high</span>
              </label>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.alert_on_target_offline || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, alert_on_target_offline: e.target.checked })}
                />
                <span>Target offline</span>
              </label>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.alert_on_ssh_error || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, alert_on_ssh_error: e.target.checked })}
                />
                <span>Errori SSH</span>
              </label>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.alert_on_install_success || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, alert_on_install_success: e.target.checked })}
                />
                <span>Installazione completata</span>
              </label>
            </div>

            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={notificationFormData.alert_on_install_failed || false}
                  onChange={e => setNotificationFormData({ ...notificationFormData, alert_on_install_failed: e.target.checked })}
                />
                <span>Installazione fallita</span>
              </label>
            </div>

            <div className="form-group">
              <label htmlFor="offline-threshold">Soglia Target Offline (minuti)</label>
              <input
                id="offline-threshold"
                type="number"
                min="1"
                max="60"
                value={notificationFormData.target_offline_threshold_minutes || 5}
                onChange={e => setNotificationFormData({ ...notificationFormData, target_offline_threshold_minutes: parseInt(e.target.value) })}
                className="input"
              />
              <span className="form-hint">Tempo prima di considerare un target offline</span>
            </div>

            <div className="form-group">
              <label htmlFor="cooldown">Cooldown Notifiche (minuti)</label>
              <input
                id="cooldown"
                type="number"
                min="5"
                max="1440"
                value={notificationFormData.cooldown_minutes || 60}
                onChange={e => setNotificationFormData({ ...notificationFormData, cooldown_minutes: parseInt(e.target.value) })}
                className="input"
              />
              <span className="form-hint">
                Intervallo minimo tra notifiche dello stesso tipo
              </span>
            </div>
          </div>
        </div>

        <div className="settings-actions">
          <button
            type="button"
            onClick={handleSaveNotifications}
            disabled={savingNotifications}
            className="btn-primary"
          >
            {savingNotifications ? 'Salvataggio...' : 'Salva Configurazione'}
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
                      <strong>Problema: {item.problem}</strong>
                      <p>Soluzione: {item.solution}</p>
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
      </>
    );
  };

  const renderSecuritySettings = () => {
    if (loadingSecurity) {
      return (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Caricamento configurazione...</p>
        </div>
      );
    }

    if (!userProfile) {
      return (
        <div className="settings-section">
          <p className="error-message">Errore nel caricamento del profilo</p>
        </div>
      );
    }

    return (
      <>
        {/* User Info */}
        <div className="settings-section">
          <h2 className="section-title">Informazioni Utente</h2>
          <p className="section-description">Dettagli dell'account corrente</p>

          <div className="settings-grid">
            <div className="form-group">
              <label>Username</label>
              <div className="info-value">{userProfile.username}</div>
            </div>

            {userProfile.email && (
              <div className="form-group">
                <label>Email</label>
                <div className="info-value">{userProfile.email}</div>
              </div>
            )}

            <div className="form-group">
              <label>Ruolo</label>
              <div className="info-value">
                {userProfile.is_superuser ? 'Superuser' : userProfile.is_staff ? 'Staff' : 'Utente'}
              </div>
            </div>

            <div className="form-group">
              <label>Data Registrazione</label>
              <div className="info-value">
                {new Date(userProfile.date_joined).toLocaleDateString('it-IT')}
              </div>
            </div>

            {userProfile.last_login && (
              <div className="form-group">
                <label>Ultimo Accesso</label>
                <div className="info-value">
                  {new Date(userProfile.last_login).toLocaleString('it-IT')}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Change Username */}
        <div className="settings-section">
          <h2 className="section-title">Cambia Username</h2>
          <p className="section-description">Modifica il tuo nome utente per il login</p>

          <div className="settings-grid">
            <div className="form-group">
              <label htmlFor="new-username">Nuovo Username</label>
              <div className="username-input-group">
                <input
                  id="new-username"
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="Nuovo username"
                  disabled={changingUsername}
                  className="input"
                />
                <button
                  className="btn-primary"
                  onClick={handleChangeUsername}
                  disabled={changingUsername || newUsername === userProfile.username || !newUsername}
                >
                  {changingUsername ? 'Salvataggio...' : 'Cambia Username'}
                </button>
              </div>
              <span className="form-hint">
                Username può contenere lettere, numeri, underscore (_) e trattini (-)
              </span>
            </div>
          </div>
        </div>

        {/* Change Password */}
        <div className="settings-section">
          <h2 className="section-title">Cambia Password</h2>
          <p className="section-description">Aggiorna la tua password di accesso</p>

          <div className="password-requirements-box">
            <h4>Requisiti Password:</h4>
            <ul>
              <li>Minimo 9 caratteri</li>
              <li>Almeno 2 lettere maiuscole</li>
              <li>Almeno 2 lettere minuscole</li>
              <li>Almeno 2 numeri</li>
              <li>Almeno 2 caratteri speciali (!@#$%^&*...)</li>
            </ul>
          </div>

          <div className="settings-grid">
            <div className="form-group">
              <label htmlFor="current-password">Password Attuale</label>
              <div className="password-input-group">
                <input
                  id="current-password"
                  type={showPasswords.current ? "text" : "password"}
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                  placeholder="Inserisci password attuale"
                  disabled={changingPassword}
                  className="input"
                />
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => togglePasswordVisibility('current')}
                  title={showPasswords.current ? "Nascondi password" : "Mostra password"}
                >
                  {showPasswords.current ? '●' : '○'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="new-password">Nuova Password</label>
              <div className="password-input-group">
                <input
                  id="new-password"
                  type={showPasswords.new ? "text" : "password"}
                  value={passwordForm.new_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                  placeholder="Inserisci nuova password"
                  disabled={changingPassword}
                  className="input"
                />
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => togglePasswordVisibility('new')}
                  title={showPasswords.new ? "Nascondi password" : "Mostra password"}
                >
                  {showPasswords.new ? '●' : '○'}
                </button>
              </div>

              {/* Password Strength Indicator */}
              {passwordForm.new_password && (
                <div className="password-strength">
                  <div className="strength-bar">
                    <div
                      className="strength-fill"
                      style={{
                        width: `${(passwordStrength.score / 6) * 100}%`,
                        backgroundColor: passwordStrength.color
                      }}
                    />
                  </div>
                  <span className="strength-label" style={{ color: passwordStrength.color }}>
                    Sicurezza: {passwordStrength.label}
                  </span>
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="confirm-password">Conferma Nuova Password</label>
              <div className="password-input-group">
                <input
                  id="confirm-password"
                  type={showPasswords.confirm ? "text" : "password"}
                  value={passwordForm.confirm_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                  placeholder="Conferma nuova password"
                  disabled={changingPassword}
                  className="input"
                />
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => togglePasswordVisibility('confirm')}
                  title={showPasswords.confirm ? "Nascondi password" : "Mostra password"}
                >
                  {showPasswords.confirm ? '●' : '○'}
                </button>
              </div>

              {/* Match indicator */}
              {passwordForm.new_password && passwordForm.confirm_password && (
                <span className={`form-hint ${passwordForm.new_password === passwordForm.confirm_password ? 'text-success' : 'text-error'}`}>
                  {passwordForm.new_password === passwordForm.confirm_password ? 'Le password corrispondono' : 'Le password non corrispondono'}
                </span>
              )}
            </div>

            <div className="form-group">
              <button
                className="btn-primary"
                onClick={handleChangePassword}
                disabled={changingPassword || !passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password}
              >
                {changingPassword ? 'Salvataggio...' : 'Cambia Password'}
              </button>
            </div>
          </div>
        </div>
      </>
    );
  };

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

  const renderAgentAPIKeysSettings = () => (
    <div className="settings-section">
      <div className="section-header-with-action">
        <div>
          <h2 className="section-title">API Keys Agent</h2>
          <p className="section-description">Gestisci le API Keys per l'autenticazione degli agent Dog</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleGenerateAgentAPIKey}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Genera Nuova API Key
        </button>
      </div>

      {loadingAgentKeys ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>Caricamento API Keys...</p>
        </div>
      ) : agentAPIKeys.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
          <h3>Nessuna API Key configurata</h3>
          <p>Genera una nuova API Key per consentire agli agent di connettersi</p>
        </div>
      ) : (
        <div className="ssh-keys-list">
          {agentAPIKeys.map(key => (
            <div key={key.id} className="ssh-key-card">
              <div className="ssh-key-header">
                <div className="ssh-key-info">
                  <h3>API Key #{key.id}</h3>
                  <div className="ssh-key-meta">
                    <span className={`badge ${key.is_active ? 'badge-success' : 'badge-danger'}`}>
                      {key.is_active ? 'Attiva' : 'Disattivata'}
                    </span>
                    {key.created_by_username && (
                      <span className="badge badge-secondary">
                        Creata da: {key.created_by_username}
                      </span>
                    )}
                    {key.last_used_at && (
                      <span className="ssh-key-targets">
                        Ultimo uso: {new Date(key.last_used_at).toLocaleString('it-IT')}
                      </span>
                    )}
                  </div>
                </div>
                <div className="ssh-key-actions">
                  <button
                    className="btn btn-ghost btn-sm btn-info"
                    onClick={() => handleShowKeyRequest(key.id)}
                    title="Mostra API Key"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  </button>
                  <button
                    className={`btn btn-ghost btn-sm ${key.is_active ? 'btn-warning' : 'btn-success'}`}
                    onClick={() => handleToggleAgentAPIKey(key.id, key.is_active)}
                    title={key.is_active ? 'Disattiva' : 'Attiva'}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      {key.is_active ? (
                        <path d="M17 10H3M21 6v8M5 6v8" />
                      ) : (
                        <path d="M9 10l3 3 7-7" />
                      )}
                    </svg>
                  </button>
                  <button
                    className="btn btn-ghost btn-sm btn-danger"
                    onClick={() => setAgentKeyToDelete(key.id)}
                    title="Elimina API Key"
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
                  <label>Hash (SHA512):</label>
                  <code>{key.key_hash ? key.key_hash.substring(0, 32) + '...' : 'N/A'}</code>
                </div>
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

      {/* Modal per mostrare la chiave generata (solo una volta) */}
      {showAgentKeyModal && generatedAPIKey && (
        <div className="modal-overlay" onClick={handleCloseGeneratedKeyModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>API Key Generata</h2>
              <button className="modal-close" onClick={handleCloseGeneratedKeyModal}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <div className="alert alert-warning" style={{ marginBottom: '1.5rem' }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <div>
                  <strong>ATTENZIONE!</strong> Salva questa API Key in un posto sicuro.
                  Non sarà più possibile visualizzarla dopo aver chiuso questa finestra.
                </div>
              </div>
              <div className="form-group">
                <label>API Key:</label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    value={generatedAPIKey}
                    readOnly
                    className="form-control"
                    style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      navigator.clipboard.writeText(generatedAPIKey);
                      showToast({ type: 'success', title: 'Copiato', message: 'API Key copiata negli appunti' });
                    }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                  </button>
                </div>
              </div>
              <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Usa questa chiave nel file di configurazione dell'agent (agent.conf) nel campo <code>api_key</code>.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-primary" onClick={handleCloseGeneratedKeyModal}>
                Ho salvato la chiave
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal conferma eliminazione */}
      {agentKeyToDelete && (
        <div className="modal-overlay" onClick={() => setAgentKeyToDelete(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Conferma Eliminazione</h2>
              <button className="modal-close" onClick={() => setAgentKeyToDelete(null)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <p>Sei sicuro di voler eliminare questa API Key?</p>
              <p style={{ marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                Gli agent che utilizzano questa chiave non potranno più connettersi al server.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setAgentKeyToDelete(null)}>
                Annulla
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleDeleteAgentAPIKey(agentKeyToDelete)}
              >
                Elimina
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal per inserire password e mostrare la chiave */}
      {showPasswordModal && (
        <div className="modal-overlay" onClick={handleClosePasswordModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Mostra API Key</h2>
              <button className="modal-close" onClick={handleClosePasswordModal}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              {!retrievedKey ? (
                <>
                  <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    <div>
                      Per motivi di sicurezza, inserisci la tua password per visualizzare la chiave.
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Password Admin:</label>
                    <input
                      type="password"
                      value={passwordForRetrieve}
                      onChange={(e) => setPasswordForRetrieve(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleRetrieveKey()}
                      placeholder="Inserisci la tua password"
                      className="form-control"
                      autoFocus
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="alert alert-success" style={{ marginBottom: '1.5rem' }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                      <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                    <div>
                      API Key recuperata con successo!
                    </div>
                  </div>
                  <div className="form-group">
                    <label>API Key:</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <input
                        type="text"
                        value={retrievedKey}
                        readOnly
                        className="form-control"
                        style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                      />
                      <button
                        className="btn btn-secondary"
                        onClick={() => {
                          navigator.clipboard.writeText(retrievedKey);
                          showToast({ type: 'success', title: 'Copiato', message: 'API Key copiata negli appunti' });
                        }}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="modal-footer">
              {!retrievedKey ? (
                <>
                  <button className="btn btn-secondary" onClick={handleClosePasswordModal}>
                    Annulla
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleRetrieveKey}
                    disabled={retrievingKey || !passwordForRetrieve}
                  >
                    {retrievingKey ? 'Verifica...' : 'Mostra Chiave'}
                  </button>
                </>
              ) : (
                <button className="btn btn-primary" onClick={handleClosePasswordModal}>
                  Chiudi
                </button>
              )}
            </div>
          </div>
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
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
          API Keys Agent
        </button>
        <button
          className={`tab ${activeTab === 'mcp' ? 'active' : ''}`}
          onClick={() => setActiveTab('mcp')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
          </svg>
          MCP
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
        {activeTab === 'notifications' && renderNotificationSettings()}
        {activeTab === 'security' && renderSecuritySettings()}
        {activeTab === 'monitoring' && renderMonitoringSettings()}
        {activeTab === 'ssh' && renderAgentAPIKeysSettings()}
        {activeTab === 'mcp' && <MCPKeysTab />}
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
