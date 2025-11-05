/**
 * Threats Service - Gestione minacce e analisi traffico
 * Security: Input validation, XSS prevention, rate limiting
 */

import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// Validazione IP
const validateIP = (ip: string): boolean => {
  const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  return ipRegex.test(ip);
};

// Sanitizzazione stringa per prevenire XSS
const sanitizeString = (str: string): string => {
  return str
    .replace(/[<>'"]/g, '')
    .trim()
    .substring(0, 500);
};

// Validazione severity
const validateSeverity = (severity: string): boolean => {
  return ['low', 'medium', 'high', 'critical'].includes(severity.toLowerCase());
};

// Validazione score (0-100)
const validateScore = (score: number): boolean => {
  return !isNaN(score) && score >= 0 && score <= 100;
};

export interface ThreatLog {
  id: number;
  target: number;
  target_hostname?: string;
  source_ip: string;
  dest_port: number | null;
  protocol: string;
  threat_score: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  packet_count: number;
  reasons: string[];
  description: string;
  country_code: string;
  is_blocked: boolean;
  is_resolved: boolean;
  resolved_at: string | null;
  detected_at: string;
  updated_at: string;
}

export interface ThreatStats {
  total_threats: number;
  critical_threats: number;
  high_threats: number;
  medium_threats: number;
  low_threats: number;
  blocked_ips: number;
  resolved_threats: number;
  unresolved_threats: number;
  top_attackers: Array<{
    source_ip: string;
    count: number;
    max_score: number;
  }>;
  recent_threats: ThreatLog[];
}

export interface ThreatsFilter {
  target?: number;
  severity?: string;
  is_blocked?: boolean;
  is_resolved?: boolean;
  source_ip?: string;
  min_score?: number;
  since?: string;
  limit?: number;
  offset?: number;
}

class ThreatsService {
  /**
   * Ottiene lista minacce con filtri
   */
  async getThreats(filters: ThreatsFilter = {}): Promise<{ count: number; results: ThreatLog[] }> {
    // Validazione filtri
    if (filters.severity && !validateSeverity(filters.severity)) {
      throw new Error('Severity non valida');
    }

    if (filters.source_ip && !validateIP(filters.source_ip)) {
      throw new Error('IP sorgente non valido');
    }

    if (filters.min_score !== undefined && !validateScore(filters.min_score)) {
      throw new Error('Score minimo non valido (0-100)');
    }

    // Limita risultati per evitare sovraccarico
    const limit = Math.min(filters.limit || 50, 200);

    try {
      const response = await axios.get(`${API_URL}/threats/`, {
        params: {
          ...filters,
          limit,
        },
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching threats:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare le minacce');
    }
  }

  /**
   * Ottiene statistiche minacce
   */
  async getStats(targetId?: number): Promise<ThreatStats> {
    try {
      const response = await axios.get(`${API_URL}/threats/stats/`, {
        params: targetId ? { target: targetId } : undefined,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching threat stats:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare statistiche');
    }
  }

  /**
   * Ottiene dettaglio singola minaccia
   */
  async getThreat(threatId: number): Promise<ThreatLog> {
    if (!Number.isInteger(threatId) || threatId < 1) {
      throw new Error('ID minaccia non valido');
    }

    try {
      const response = await axios.get(`${API_URL}/threats/${threatId}/`);
      return response.data;
    } catch (error: any) {
      console.error('Error fetching threat:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare la minaccia');
    }
  }

  /**
   * Risolve una minaccia
   */
  async resolveThreat(threatId: number, notes?: string): Promise<{ message: string }> {
    if (!Number.isInteger(threatId) || threatId < 1) {
      throw new Error('ID minaccia non valido');
    }

    const sanitizedNotes = notes ? sanitizeString(notes) : undefined;

    try {
      const response = await axios.post(`${API_URL}/threats/${threatId}/resolve/`, {
        notes: sanitizedNotes,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error resolving threat:', error);
      throw new Error(error.response?.data?.error || 'Impossibile risolvere la minaccia');
    }
  }

  /**
   * Blocca un IP manualmente
   */
  async blockIP(targetId: number, ipAddress: string, reason?: string): Promise<{ message: string }> {
    if (!validateIP(ipAddress)) {
      throw new Error('Indirizzo IP non valido');
    }

    const sanitizedReason = reason ? sanitizeString(reason) : undefined;

    try {
      const response = await axios.post(`${API_URL}/targets/${targetId}/block-ip/`, {
        ip_address: ipAddress,
        reason: sanitizedReason,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error blocking IP:', error);
      throw new Error(error.response?.data?.error || 'Impossibile bloccare IP');
    }
  }

  /**
   * Sblocca un IP
   */
  async unblockIP(targetId: number, ipAddress: string): Promise<{ message: string }> {
    if (!validateIP(ipAddress)) {
      throw new Error('Indirizzo IP non valido');
    }

    try {
      const response = await axios.post(`${API_URL}/targets/${targetId}/unblock-ip/`, {
        ip_address: ipAddress,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error unblocking IP:', error);
      throw new Error(error.response?.data?.error || 'Impossibile sbloccare IP');
    }
  }

  /**
   * Analizza traffico bloccato
   */
  async analyzeTraffic(targetId: number, hours: number = 1): Promise<any> {
    if (!Number.isInteger(hours) || hours < 1 || hours > 168) {
      throw new Error('Ore non valide (1-168)');
    }

    try {
      const response = await axios.post(`${API_URL}/targets/${targetId}/analyze-traffic/`, {
        hours,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error analyzing traffic:', error);
      throw new Error(error.response?.data?.error || 'Impossibile analizzare traffico');
    }
  }
}

export default new ThreatsService();
