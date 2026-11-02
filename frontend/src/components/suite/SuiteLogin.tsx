/**
 * Login standard SentinelSuite.
 *
 * Questo file e SuiteLogin.css sono IDENTICI in tutti i tool della suite:
 * una modifica qui va replicata negli altri repo. Ogni tool mette solo la
 * propria logica di autenticazione nella sua pages/Login.tsx; l'unica
 * differenza visiva e' il colore, scelto dalla prop `tool`.
 */

import React, { useState } from 'react';
import suiteLogo from './assets/sentinelsuite.svg';
import toolLogo from './assets/tool.svg';
import './SuiteLogin.css';

export type SuiteTool = 'sentinelcore' | 'firedog' | 'cybershepherd' | 'intellidog';

export interface SuiteFooterText {
  product: string;
  disclaimer: string;
  rights: string;
}

interface SuiteLoginLayoutProps {
  tool: SuiteTool;
  name: string;
  subtitle: string;
  footer: SuiteFooterText;
  children: React.ReactNode;
}

interface SuitePasswordFieldProps {
  label: string;
  showLabel: string;
  hideLabel: string;
  value: string;
  disabled: boolean;
  placeholder?: string;
  onChange: (value: string) => void;
}

const SUITE_SITE = 'https://sentinelsuite.dognet-technologies.online';
const SUITE_SITE_LABEL = 'sentinelsuite.dognet-technologies.online';
const COMPANY_SITE = 'https://dognet.tech';
const COMPANY_SITE_LABEL = 'dognet.tech';
const COMPANY_EMAIL = 'info@dognet.tech';
const COMPANY_LEGAL =
  'Dognet Technologies S.r.l. · Via XXV Aprile 47, 24055 Cologno al Serio (BG) · P.IVA 04867480164 · REA BG-495176';

function EyeIcon({ crossed }: { crossed: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
      {crossed && <line x1="4" y1="4" x2="20" y2="20" />}
    </svg>
  );
}

export function SuitePasswordField({
  label,
  showLabel,
  hideLabel,
  value,
  disabled,
  placeholder,
  onChange,
}: SuitePasswordFieldProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <label className="ss-login__field">
      <span className="ss-login__label">{label}</span>
      <div className="ss-login__input-wrap">
        <input
          className="ss-login__input ss-login__input--password"
          name="password"
          type={isVisible ? 'text' : 'password'}
          autoComplete="current-password"
          required
          disabled={disabled}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
        <button
          type="button"
          className="ss-login__toggle"
          onClick={() => setIsVisible((visible) => !visible)}
          aria-label={isVisible ? hideLabel : showLabel}
          tabIndex={-1}
        >
          <EyeIcon crossed={isVisible} />
        </button>
      </div>
    </label>
  );
}

export function SuiteAlert({ children }: { children: React.ReactNode }) {
  return (
    <div className="ss-login__alert" role="alert">
      <span aria-hidden="true">⚠</span>
      <span>{children}</span>
    </div>
  );
}

function SuiteFooter({ footer }: { footer: SuiteFooterText }) {
  return (
    <footer className="ss-login__footer">
      <div className="ss-login__footer-brand">
        <img src={suiteLogo} alt="" width="20" height="19" />
        <strong>SentinelSuite</strong>
        <span>{footer.product}</span>
      </div>
      <p className="ss-login__footer-text">{footer.disclaimer}</p>
      <p className="ss-login__footer-text">
        © {new Date().getFullYear()} {COMPANY_LEGAL}. {footer.rights}
      </p>
      <nav className="ss-login__footer-links" aria-label="Dognet Technologies">
        <a href={SUITE_SITE} target="_blank" rel="noopener noreferrer">{SUITE_SITE_LABEL}</a>
        <a href={COMPANY_SITE} target="_blank" rel="noopener noreferrer">{COMPANY_SITE_LABEL}</a>
        <a href={`mailto:${COMPANY_EMAIL}`}>{COMPANY_EMAIL}</a>
      </nav>
    </footer>
  );
}

export function SuiteLoginLayout({ tool, name, subtitle, footer, children }: SuiteLoginLayoutProps) {
  return (
    <div className="ss-login" data-tool={tool}>
      <main className="ss-login__main">
        <div className="ss-login__panel">
          <header className="ss-login__brand">
            <div className="ss-login__logo">
              <img src={toolLogo} alt="" width="34" height="34" />
            </div>
            <div>
              <h1 className="ss-login__title">{name}</h1>
              <p className="ss-login__subtitle">{subtitle}</p>
            </div>
          </header>
          {children}
        </div>
      </main>
      <SuiteFooter footer={footer} />
    </div>
  );
}
