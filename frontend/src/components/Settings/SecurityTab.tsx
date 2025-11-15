/**
 * SecurityTab Component
 * Tab per gestione utente (username, password)
 * 
 * File: frontend/src/components/Settings/SecurityTab.tsx
 */
import React, { useState, useEffect } from 'react';
import apiService from '../../services/api';
import { useNotifications } from '../../contexts/NotificationContext';
import { useAuth } from '../../contexts/AuthContext';

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

const SecurityTab: React.FC = () => {
  const { showToast, showConfirm } = useNotifications();
  const { user } = useAuth();
  
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Cambio username
  const [newUsername, setNewUsername] = useState('');
  const [changingUsername, setChangingUsername] = useState(false);
  
  // Cambio password
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
  
  // Password strength indicator
  const [passwordStrength, setPasswordStrength] = useState({
    score: 0,
    label: '',
    color: ''
  });

  useEffect(() => {
    loadProfile();
  }, []);

  useEffect(() => {
    if (passwordForm.new_password) {
      checkPasswordStrength(passwordForm.new_password);
    } else {
      setPasswordStrength({ score: 0, label: '', color: '' });
    }
  }, [passwordForm.new_password]);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await apiService.getUserProfile();
      setProfile(data);
      setNewUsername(data.username);
    } catch (error: any) {
      showToast({
        type: 'error',
        title: 'Errore',
        message: 'Impossibile caricare profilo utente'
      });
    } finally {
      setLoading(false);
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
    if (!newUsername || newUsername === profile?.username) {
      return;
    }

    showConfirm({
      title: 'Conferma Cambio Username',
      message: `Vuoi cambiare il tuo username da "${profile?.username}" a "${newUsername}"?`,
      confirmText: 'Cambia Username',
      type: 'warning',
      onConfirm: async () => {
        try {
          setChangingUsername(true);
          await apiService.changeUsername(newUsername);
          
          showToast({
            type: 'success',
            title: 'Username Aggiornato',
            message: `Il tuo username è stato cambiato in "${newUsername}"`
          });
          
          // Ricarica profilo
          await loadProfile();
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
          setNewUsername(profile?.username || '');
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
          await apiService.changePassword(passwordForm);
          
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

  if (loading) {
    return (
      <div className="settings-tab">
        <div className="loading-spinner">Caricamento...</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="settings-tab">
        <div className="error-message">Errore nel caricamento del profilo</div>
      </div>
    );
  }

  return (
    <div className="settings-tab security-tab">
      
      {/* User Info */}
      <div className="settings-section">
        <div className="section-header">
          <h3>👤 Informazioni Utente</h3>
        </div>

        <div className="user-info-grid">
          <div className="info-item">
            <label>Username</label>
            <span className="info-value">{profile.username}</span>
          </div>
          
          {profile.email && (
            <div className="info-item">
              <label>Email</label>
              <span className="info-value">{profile.email}</span>
            </div>
          )}
          
          <div className="info-item">
            <label>Ruolo</label>
            <span className="info-value">
              {profile.is_superuser ? '🔑 Superuser' : profile.is_staff ? '👨‍💼 Staff' : '👤 Utente'}
            </span>
          </div>
          
          <div className="info-item">
            <label>Data Registrazione</label>
            <span className="info-value">
              {new Date(profile.date_joined).toLocaleDateString('it-IT')}
            </span>
          </div>
          
          {profile.last_login && (
            <div className="info-item">
              <label>Ultimo Accesso</label>
              <span className="info-value">
                {new Date(profile.last_login).toLocaleString('it-IT')}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Change Username */}
      <div className="settings-section">
        <div className="section-header">
          <h3>✏️ Cambia Username</h3>
          <p className="section-description">
            Modifica il tuo nome utente per il login
          </p>
        </div>

        <div className="form-group">
          <label>Nuovo Username</label>
          <div className="username-input-group">
            <input
              type="text"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="Nuovo username"
              disabled={changingUsername}
            />
            <button
              className="btn-primary"
              onClick={handleChangeUsername}
              disabled={changingUsername || newUsername === profile.username || !newUsername}
            >
              {changingUsername ? '⏳ Salvataggio...' : '✏️ Cambia Username'}
            </button>
          </div>
          <small className="form-hint">
            Username può contenere lettere, numeri, underscore (_) e trattini (-)
          </small>
        </div>
      </div>

      {/* Change Password */}
      <div className="settings-section">
        <div className="section-header">
          <h3>🔒 Cambia Password</h3>
          <p className="section-description">
            Aggiorna la tua password di accesso
          </p>
        </div>

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

        <div className="form-group">
          <label>Password Attuale</label>
          <div className="password-input-group">
            <input
              type={showPasswords.current ? "text" : "password"}
              value={passwordForm.current_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
              placeholder="Inserisci password attuale"
              disabled={changingPassword}
            />
            <button
              type="button"
              className="btn-icon"
              onClick={() => togglePasswordVisibility('current')}
            >
              {showPasswords.current ? '👁️' : '👁️‍🗨️'}
            </button>
          </div>
        </div>

        <div className="form-group">
          <label>Nuova Password</label>
          <div className="password-input-group">
            <input
              type={showPasswords.new ? "text" : "password"}
              value={passwordForm.new_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
              placeholder="Inserisci nuova password"
              disabled={changingPassword}
            />
            <button
              type="button"
              className="btn-icon"
              onClick={() => togglePasswordVisibility('new')}
            >
              {showPasswords.new ? '👁️' : '👁️‍🗨️'}
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
          <label>Conferma Nuova Password</label>
          <div className="password-input-group">
            <input
              type={showPasswords.confirm ? "text" : "password"}
              value={passwordForm.confirm_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
              placeholder="Conferma nuova password"
              disabled={changingPassword}
            />
            <button
              type="button"
              className="btn-icon"
              onClick={() => togglePasswordVisibility('confirm')}
            >
              {showPasswords.confirm ? '👁️' : '👁️‍🗨️'}
            </button>
          </div>
          
          {/* Match indicator */}
          {passwordForm.new_password && passwordForm.confirm_password && (
            <small className={`form-hint ${passwordForm.new_password === passwordForm.confirm_password ? 'text-success' : 'text-error'}`}>
              {passwordForm.new_password === passwordForm.confirm_password ? '✓ Le password corrispondono' : '✗ Le password non corrispondono'}
            </small>
          )}
        </div>

        <div className="form-actions">
          <button
            className="btn-primary btn-large"
            onClick={handleChangePassword}
            disabled={changingPassword || !passwordForm.current_password || !passwordForm.new_password || !passwordForm.confirm_password}
          >
            {changingPassword ? '⏳ Salvataggio...' : '🔒 Cambia Password'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SecurityTab;
