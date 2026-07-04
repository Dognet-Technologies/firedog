/**
 * Login Page — riscritto da zero per leggibilità.
 *
 * Note di design:
 * - Inputs con background pieno + testo ad alto contrasto, niente vetro/blur
 *   sopra al testo (era la causa della precedente illeggibilità).
 * - Stato di errore inline sotto al form; nessuna riga "neon" ovunque.
 * - Niente dipendenze esterne, niente icone SVG complesse — un solo eye-toggle
 *   per password come carattere unicode.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './Login.css';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setError('');
    setLoading(true);
    try {
      await login({ username: username.trim(), password });
      navigate('/dashboard');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string; non_field_errors?: string[] } } })
          ?.response?.data?.detail ||
        (err as { response?: { data?: { non_field_errors?: string[] } } })
          ?.response?.data?.non_field_errors?.[0] ||
        'Credenziali non valide. Riprova.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fd-login">
      <div className="fd-login__panel">
        <header className="fd-login__brand">
          <div className="fd-login__logo" aria-hidden="true">🔥</div>
          <div>
            <h1 className="fd-login__title">FireDog</h1>
            <p className="fd-login__subtitle">Centralized Firewall Management</p>
          </div>
        </header>

        <form className="fd-login__form" onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="fd-login__alert" role="alert">
              <span aria-hidden="true">⚠</span>
              <span>{error}</span>
            </div>
          )}

          <label className="fd-login__field">
            <span className="fd-login__label">Username</span>
            <input
              className="fd-login__input"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              autoFocus
              required
              disabled={loading}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="es. admin"
            />
          </label>

          <label className="fd-login__field">
            <span className="fd-login__label">Password</span>
            <div className="fd-login__input-wrap">
              <input
                className="fd-login__input fd-login__input--password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
              <button
                type="button"
                className="fd-login__toggle"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? 'Nascondi password' : 'Mostra password'}
                tabIndex={-1}
              >
                {showPassword ? '🙈' : '👁'}
              </button>
            </div>
          </label>

          <label className="fd-login__remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              disabled={loading}
            />
            <span>Ricordami su questo browser</span>
          </label>

          <button type="submit" className="fd-login__submit" disabled={loading || !username || !password}>
            {loading ? 'Accesso…' : 'Accedi'}
          </button>
        </form>

        <footer className="fd-login__footer">
          <span>FireDog · Secure Firewall Management</span>
        </footer>
      </div>
    </div>
  );
};

export default Login;
