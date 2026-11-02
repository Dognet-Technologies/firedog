/** Login FireDog: solo la logica di autenticazione, la pagina e' lo standard SentinelSuite. */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  SuiteAlert,
  SuiteFooterText,
  SuiteLoginLayout,
  SuitePasswordField,
} from '../components/suite/SuiteLogin';

const FOOTER_TEXT: SuiteFooterText = {
  product: 'è un prodotto di Dognet Technologies',
  disclaimer:
    'Accesso riservato agli utenti autorizzati. Ogni utilizzo non autorizzato è vietato e potrà essere perseguito a norma di legge.',
  rights: 'Tutti i diritti riservati.',
};

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
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
    <SuiteLoginLayout
      tool="firedog"
      name="FireDog"
      subtitle="Centralized Firewall Management"
      footer={FOOTER_TEXT}
    >
      <form className="ss-login__form" onSubmit={handleSubmit} noValidate>
        {error && <SuiteAlert>{error}</SuiteAlert>}

        <label className="ss-login__field">
          <span className="ss-login__label">Username</span>
          <input
            className="ss-login__input"
            name="username"
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

        <SuitePasswordField
          label="Password"
          showLabel="Mostra password"
          hideLabel="Nascondi password"
          value={password}
          disabled={loading}
          placeholder="••••••••"
          onChange={setPassword}
        />

        <button type="submit" className="ss-login__submit" disabled={loading || !username || !password}>
          {loading ? 'Accesso…' : 'Accedi'}
        </button>
      </form>
    </SuiteLoginLayout>
  );
};

export default Login;
