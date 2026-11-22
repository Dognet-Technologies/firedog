// ============================================================================
// Certificato del master: la CA locale dell'installazione di cui gli agent
// si fidano (ca_cert in agent.conf) e che il browser può importare. Dati da
// /api/settings/tls/ (tls-info.json di deploy/firedog-tls), CA scaricabile da
// /api/tls/ca.pem; chi la scarica la conferma con l'impronta SHA-256.
// ============================================================================

import React, { useEffect, useState } from 'react';
import api, { TlsInfo } from '../../services/api';
import './MasterCertificateCard.css';

const date = (v?: string) => (v ? new Date(v).toLocaleDateString('it-IT') : '—');

export default function MasterCertificateCard() {
  const [info, setInfo] = useState<TlsInfo | null>(null);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    api.getTlsInfo()
      .then((data) => { if (active) setInfo(data); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);

  if (failed) return <p className="master-cert-error">Impossibile leggere il certificato del master.</p>;
  if (!info) return null;
  if (!info.managed) {
    return (
      <section className="master-cert master-cert-unmanaged">
        Certificato TLS non gestito da FireDog: fornito dall&apos;amministratore (PKI aziendale) o
        installazione senza HTTPS. Gli agent vanno configurati con la CA che l&apos;ha emesso.
      </section>
    );
  }

  const testing = info.profile === 'testing';
  const copy = async () => {
    if (!info.ca_fingerprint_sha256) return;
    try {
      await navigator.clipboard.writeText(info.ca_fingerprint_sha256);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className={`master-cert${testing ? ' master-cert-testing' : ''}`} aria-labelledby="master-cert-title">
      <header className="master-cert-header">
        <h3 id="master-cert-title">Certificato del master</h3>
        {testing && <span className="master-cert-badge">TESTING — solo uso interno</span>}
      </header>
      <p className="master-cert-hint">
        Gli agent verificano il master con la CA di questa installazione: scaricala e impostala in{' '}
        <code>ca_cert</code> nella sezione <code>[agent]</code> di <code>agent.conf</code> (se l&apos;agent
        parla anche con altri prodotti della suite, metti le loro CA nello stesso file). Prima di usarla
        confronta l&apos;impronta qui sotto con quella del file scaricato.
      </p>
      <dl className="master-cert-grid">
        <dt>Impronta SHA-256 della CA</dt>
        <dd className="master-cert-fp">
          <code>{info.ca_fingerprint_sha256}</code>
          <button type="button" className="btn btn-ghost btn-sm" onClick={copy}
            aria-label="Copia l'impronta" title="Copia l'impronta">
            {copied ? 'Copiata' : 'Copia'}
          </button>
        </dd>
        <dt>CA</dt>
        <dd>{info.ca_subject} · scade il {date(info.ca_not_after)}</dd>
        <dt>Certificato server</dt>
        <dd>{info.server_name} · scade il {date(info.server_not_after)} (rinnovo automatico)</dd>
      </dl>
      <a className="btn btn-primary btn-sm master-cert-download" href="/api/tls/ca.pem" download="firedog-ca.pem">
        Scarica la CA (firedog-ca.pem)
      </a>
    </section>
  );
}
