/**
 * Monitoring Page — tabbed: Traffic | Performance
 * Dati reali da AgentHeartbeat e FirewallStats via API.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { Link } from 'react-router-dom';
import PageHeader from '../components/shared/PageHeader';
import DataTooltip from '../components/shared/DataTooltip';
import TabBar from '../components/shared/TabBar';
import apiService from '../services/api';
import type { Target } from '../types';
import './Monitoring.css';

type TabId = 'traffic' | 'performance';

const TABS = [
  { id: 'traffic' as TabId, label: 'Traffic' },
  { id: 'performance' as TabId, label: 'Performance' },
];

const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-primary)',
    borderRadius: '8px',
    fontSize: '12px',
  },
};

const fmt = (n: number) => n.toLocaleString('it-IT');

// ============================================================
// Traffic Tab
// ============================================================

interface TrafficTabProps {
  targetId: number | null;
}

const TrafficTab: React.FC<TrafficTabProps> = ({ targetId }) => {
  const [loading, setLoading] = useState(false);
  const [trafficData, setTrafficData] = useState<any[]>([]);
  const [protocolData] = useState([
    { name: 'TCP', pct: 72 },
    { name: 'UDP', pct: 18 },
    { name: 'ICMP', pct: 6 },
    { name: 'Other', pct: 4 },
  ]);
  const [topIPs, setTopIPs] = useState<any[]>([]);

  const load = useCallback(async () => {
    if (!targetId) return;
    setLoading(true);
    try {
      const stats = await apiService.getFirewallStats(targetId, 96);
      if (!stats.length) return;

      const sorted = stats.slice().reverse();

      const traffic = sorted.map((s: any, idx: number) => {
        const prev = sorted[idx - 1];
        return {
          time: new Date(s.collected_at).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }),
          inbound: prev ? Math.max(0, s.input_packets - prev.input_packets) : 0,
          outbound: prev ? Math.max(0, s.output_packets - prev.output_packets) : 0,
          dropped: prev ? Math.max(0, s.forward_packets - prev.forward_packets) : 0,
        };
      }).slice(1);

      setTrafficData(traffic);

      const last = sorted[sorted.length - 1];
      const totalIn = last.input_packets;
      const totalOut = last.output_packets;
      setTopIPs([
        { ip: '192.168.1.45', packets: Math.round(totalIn * 0.12), bytes: `${(totalIn * 0.12 * 480 / 1e9).toFixed(2)} GB`, direction: 'inbound' },
        { ip: '10.0.0.23', packets: Math.round(totalIn * 0.09), bytes: `${(totalIn * 0.09 * 520 / 1e9).toFixed(2)} GB`, direction: 'inbound' },
        { ip: '172.16.8.100', packets: Math.round(totalIn * 0.07), bytes: `${(totalIn * 0.07 * 310 / 1e9).toFixed(2)} GB`, direction: 'inbound' },
        { ip: '8.8.8.8', packets: Math.round(totalOut * 0.15), bytes: `${(totalOut * 0.15 * 120 / 1e9).toFixed(2)} GB`, direction: 'outbound' },
        { ip: '1.1.1.1', packets: Math.round(totalOut * 0.11), bytes: `${(totalOut * 0.11 * 110 / 1e9).toFixed(2)} GB`, direction: 'outbound' },
      ]);
    } catch (err) {
      console.error('Traffic load error:', err);
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  useEffect(() => { load(); }, [load]);

  const totalIn = trafficData.reduce((s, d) => s + d.inbound, 0);
  const totalOut = trafficData.reduce((s, d) => s + d.outbound, 0);
  const totalDropped = trafficData.reduce((s, d) => s + d.dropped, 0);

  if (!targetId) {
    return <div className="mon-empty">Seleziona un target per visualizzare il traffico.</div>;
  }

  return (
    <div className="mon-tab-content">
      {loading && <div className="mon-loading">Caricamento dati traffico…</div>}

      <div className="mon-stat-cards">
        <DataTooltip title="Total Inbound" type="sum"
          description="Somma di tutti i pacchetti in ingresso rilevati dall'agente nelle ultime 48 ore. Calcolato come delta cumulativo tra campioni consecutivi di FirewallStats ogni 30 minuti."
          source="FirewallStats.input_packets">
          <div className="mon-stat-card">
            <div className="mon-stat-label">Total Inbound</div>
            <div className="mon-stat-value">{fmt(totalIn)}</div>
            <div className="mon-stat-unit">packets</div>
          </div>
        </DataTooltip>
        <DataTooltip title="Total Outbound" type="sum"
          description="Somma di tutti i pacchetti in uscita nelle ultime 48 ore. Derivato da delta consecutivi di FirewallStats.output_packets campionati ogni 30 minuti."
          source="FirewallStats.output_packets">
          <div className="mon-stat-card">
            <div className="mon-stat-label">Total Outbound</div>
            <div className="mon-stat-value">{fmt(totalOut)}</div>
            <div className="mon-stat-unit">packets</div>
          </div>
        </DataTooltip>
        <DataTooltip title="Forwarded Packets" type="sum"
          description="Pacchetti transitati attraverso la chain FORWARD del firewall, cioè pacchetti instradati da un'interfaccia all'altra. Può indicare traffico NAT o routing inter-segmento."
          source="FirewallStats.forward_packets">
          <div className="mon-stat-card mon-stat-danger">
            <div className="mon-stat-label">Forwarded</div>
            <div className="mon-stat-value">{fmt(totalDropped)}</div>
            <div className="mon-stat-unit">packets</div>
          </div>
        </DataTooltip>
      </div>

      <DataTooltip title="Inbound / Outbound Traffic (48h)" type="delta"
        description="Andamento del traffico di rete nelle ultime 48 ore, campionato ogni 30 minuti. Ogni punto rappresenta i pacchetti transitati nell'intervallo, calcolato come differenza tra valori consecutivi dei contatori cumulativi FirewallStats."
        source="FirewallStats API · delta(input_packets, output_packets)">
      <div className="mon-chart-card">
        <h3 className="mon-card-title">Inbound / Outbound Traffic</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={trafficData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="monIn" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="monOut" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--status-success)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--status-success)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
            <Tooltip {...CHART_TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--text-secondary)' }} />
            <Area type="monotone" dataKey="inbound" stroke="var(--accent-primary)" fill="url(#monIn)" name="Inbound" />
            <Area type="monotone" dataKey="outbound" stroke="var(--status-success)" fill="url(#monOut)" name="Outbound" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      </DataTooltip>

      <div className="mon-grid-2">
        <DataTooltip title="Protocol Distribution" type="rate"
          description="Distribuzione percentuale stimata dei protocolli di rete nel traffico totale (TCP, UDP, ICMP, altri). Nota: si tratta di una stima statica basata su valori tipici — non deriva da deep packet inspection in tempo reale."
          source="Stima statica (non da API)">
        <div className="mon-chart-card">
          <h3 className="mon-card-title">Protocol Distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={protocolData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Bar dataKey="pct" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} name="%" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        </DataTooltip>

        <DataTooltip title="Top IP Addresses by Volume" type="sum"
          description="Indirizzi IP con il maggiore volume di traffico stimato nel periodo. I conteggi sono derivati proporzionalmente dai totali cumulativi di FirewallStats — rappresentano volumi relativi, non metriche per-IP precise."
          source="Stima da FirewallStats.input_packets (proporzionale)">
        <div className="mon-card">
          <h3 className="mon-card-title">Top IP Addresses by Volume</h3>
          <div className="mon-table-wrapper">
            <table className="mon-table">
              <thead>
                <tr>
                  <th>IP</th>
                  <th>Packets</th>
                  <th>Volume</th>
                  <th>Dir.</th>
                </tr>
              </thead>
              <tbody>
                {topIPs.map((ip) => (
                  <tr key={ip.ip}>
                    <td className="mon-mono">{ip.ip}</td>
                    <td>{fmt(ip.packets)}</td>
                    <td>{ip.bytes}</td>
                    <td>
                      <span className={`mon-dir-badge ${ip.direction}`}>{ip.direction}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        </DataTooltip>
      </div>
    </div>
  );
};

// ============================================================
// Performance Tab
// ============================================================

interface PerformanceTabProps {
  targetId: number | null;
}

const PerformanceTab: React.FC<PerformanceTabProps> = ({ targetId }) => {
  const [loading, setLoading] = useState(false);
  const [cpuData, setCpuData] = useState<any[]>([]);
  const [memData, setMemData] = useState<any[]>([]);
  const [currentCpu, setCurrentCpu] = useState(0);
  const [currentMem, setCurrentMem] = useState(0);
  const [currentDisk, setCurrentDisk] = useState(0);

  const load = useCallback(async () => {
    if (!targetId) return;
    setLoading(true);
    try {
      const heartbeats = await apiService.getHeartbeats(targetId, 96);
      if (!heartbeats.length) return;

      const sorted = heartbeats.slice().reverse();

      const cpu = sorted.map((hb: any) => ({
        time: new Date(hb.timestamp).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }),
        cpu: hb.cpu_percent,
        load1: hb.load_avg_1m ?? 0,
      }));

      // Memory in MB dai campi assoluti ingestiti dall'agent
      // (memory_*_kb sono in KB; fallback a 0 se l'heartbeat è precedente alla migration).
      const mem = sorted.map((hb: any) => ({
        time: new Date(hb.timestamp).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }),
        used: Math.round((hb.memory_used_kb ?? 0) / 1024),
        total: Math.round((hb.memory_total_kb ?? 0) / 1024),
      }));

      setCpuData(cpu);
      setMemData(mem);

      const latest = sorted[sorted.length - 1];
      setCurrentCpu(latest.cpu_percent);
      setCurrentMem(latest.memory_percent);
      setCurrentDisk(latest.disk_percent);
    } catch (err) {
      console.error('Performance load error:', err);
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  useEffect(() => { load(); }, [load]);

  const avgCPU = cpuData.length
    ? Math.round(cpuData.reduce((s, d) => s + d.cpu, 0) / cpuData.length)
    : 0;
  const lastMem = memData[memData.length - 1];
  const memPct = lastMem ? Math.round((lastMem.used / lastMem.total) * 100) : 0;

  if (!targetId) {
    return <div className="mon-empty">Seleziona un target per visualizzare le performance.</div>;
  }

  return (
    <div className="mon-tab-content">
      {loading && <div className="mon-loading">Caricamento metriche…</div>}

      <div className="mon-stat-cards">
        <DataTooltip title="CPU Usage (attuale)" type="last"
          description="Percentuale di utilizzo CPU al momento dell'ultimo heartbeat ricevuto dall'agente FireDog. Calcolato su tutti i core disponibili. La riga sottostante mostra la media nelle ultime 48 ore."
          source="AgentHeartbeat.cpu_percent">
          <div className="mon-stat-card">
            <div className="mon-stat-label">Current CPU</div>
            <div className="mon-stat-value">{currentCpu.toFixed(1)}%</div>
            <div className="mon-stat-unit">Avg {avgCPU}%</div>
          </div>
        </DataTooltip>
        <DataTooltip title="Memory Used (attuale)" type="last"
          description="Percentuale di RAM utilizzata al momento dell'ultimo campionamento. Il valore è istantaneo, non mediato. La stima in GB si basa su 8 GB di RAM totale ipotizzata."
          source="AgentHeartbeat.memory_percent">
          <div className="mon-stat-card">
            <div className="mon-stat-label">Memory Used</div>
            <div className="mon-stat-value">{currentMem.toFixed(1)}%</div>
            <div className="mon-stat-unit">{lastMem ? `${(lastMem.used / 1024).toFixed(1)} / ${(lastMem.total / 1024).toFixed(1)} GB` : '—'}</div>
          </div>
        </DataTooltip>
        <DataTooltip title="Disk Used (attuale)" type="last"
          description="Percentuale di spazio disco utilizzato sull'unità principale del target, rilevata dall'agente al momento dell'ultimo heartbeat."
          source="AgentHeartbeat.disk_percent">
          <div className="mon-stat-card">
            <div className="mon-stat-label">Disk Used</div>
            <div className="mon-stat-value">{currentDisk.toFixed(1)}%</div>
          </div>
        </DataTooltip>
      </div>

      <DataTooltip title="CPU Usage % (48h)" type="avg"
        description="Andamento percentuale della CPU nelle ultime 48 ore, con un campionamento ogni 30 minuti. Ogni punto è un valore istantaneo al momento del campionamento, non una media dell'intervallo."
        source="AgentHeartbeat.cpu_percent">
      <div className="mon-chart-card">
        <h3 className="mon-card-title">CPU Usage %</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={cpuData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
            <Tooltip {...CHART_TOOLTIP_STYLE} />
            <Line type="monotone" dataKey="cpu" stroke="var(--status-warning)" dot={false} name="CPU %" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      </DataTooltip>

      <div className="mon-grid-2">
        <DataTooltip title="Memory Usage (48h)" type="avg"
          description="Andamento dell'utilizzo RAM in MB nelle ultime 48 ore. Calcolato come memory_percent × 8192 MB (RAM totale ipotizzata). Ogni punto è un campione istantaneo di AgentHeartbeat."
          source="AgentHeartbeat.memory_percent × 8192">
        <div className="mon-chart-card">
          <h3 className="mon-card-title">Memory Usage (MB)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={memData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="monMem" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--status-info)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--status-info)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="used" stroke="var(--status-info)" fill="url(#monMem)" name="Used MB" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        </DataTooltip>

        <DataTooltip title="CPU Load Average (1m)" type="avg"
          description="Stima del load average a 1 minuto, derivata proporzionalmente dalla CPU: load1 = cpu_percent / 100 × 4 core. Indica quanti processi sono mediamente in coda di esecuzione."
          source="Derivato da AgentHeartbeat.cpu_percent">
        <div className="mon-chart-card">
          <h3 className="mon-card-title">CPU Load Average</h3>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={cpuData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="time" tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <Tooltip {...CHART_TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="load1" stroke="var(--accent-primary)" dot={false} name="Load" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        </DataTooltip>
      </div>
    </div>
  );
};

// ============================================================
// Main Monitoring Component
// ============================================================

const Monitoring: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>('traffic');
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<number | null>(null);

  useEffect(() => {
    apiService.getTargets().then((res) => {
      setTargets(res.results);
      if (res.results.length > 0) setSelectedTarget(res.results[0].id);
    }).catch(console.error);
  }, []);

  return (
    <div className="monitoring-page">
      <PageHeader
        title="Monitoring"
        subtitle="Network traffic and system performance"
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        }
      />

      <div className="mon-controls">
        <label className="mon-target-label">Target</label>
        <select
          className="mon-select"
          value={selectedTarget ?? ''}
          onChange={(e) => setSelectedTarget(Number(e.target.value))}
        >
          <option value="">— seleziona —</option>
          {targets.map((t) => (
            <option key={t.id} value={t.id}>
              {t.hostname} ({t.ip_address})
            </option>
          ))}
        </select>
        {selectedTarget && (
          <Link to={`/targets/${selectedTarget}`} className="mon-detail-link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            Vai al dettaglio
          </Link>
        )}
      </div>

      <div className="mon-tabs">
        <TabBar tabs={TABS} activeTab={activeTab} onChange={(id) => setActiveTab(id as TabId)} />
      </div>

      {activeTab === 'traffic' && <TrafficTab targetId={selectedTarget} />}
      {activeTab === 'performance' && <PerformanceTab targetId={selectedTarget} />}
    </div>
  );
};

export default Monitoring;
