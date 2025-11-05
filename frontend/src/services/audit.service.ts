/**
 * Audit Service - Log di sistema e azioni utente
 * Security: Input validation, sanitization, access control
 */

import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// Sanitizzazione stringa
const sanitizeString = (str: string): string => {
  return str
    .replace(/[<>'"]/g, '')
    .trim()
    .substring(0, 200);
};

// Validazione username (alfanumerico + underscore, max 100 char)
const validateUsername = (username: string): boolean => {
  const usernameRegex = /^[a-zA-Z0-9_]{1,100}$/;
  return usernameRegex.test(username);
};

// Validazione action (alfanumerico + punto, max 255 char)
const validateAction = (action: string): boolean => {
  const actionRegex = /^[a-zA-Z0-9._-]{1,255}$/;
  return actionRegex.test(action);
};

// Validazione data ISO
const validateISODate = (dateStr: string): boolean => {
  const date = new Date(dateStr);
  return !isNaN(date.getTime());
};

export interface AuditLog {
  id: number;
  username: string;
  action: string;
  target: {
    id: number;
    hostname: string;
    ip_address: string;
  } | null;
  details: any;
  ip_address: string | null;
  timestamp: string;
}

export interface AuditFilter {
  username?: string;
  action?: string;
  target_id?: number;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export interface AuditStats {
  total_actions: number;
  unique_users: number;
  actions_by_type: { [key: string]: number };
  recent_actions: AuditLog[];
}

class AuditService {
  /**
   * Ottiene log audit con filtri
   */
  async getAuditLogs(filters: AuditFilter = {}): Promise<{ count: number; results: AuditLog[] }> {
    // Validazione filtri
    if (filters.username && !validateUsername(filters.username)) {
      throw new Error('Username non valido');
    }

    if (filters.action && !validateAction(filters.action)) {
      throw new Error('Action non valida');
    }

    if (filters.since && !validateISODate(filters.since)) {
      throw new Error('Data since non valida');
    }

    if (filters.until && !validateISODate(filters.until)) {
      throw new Error('Data until non valida');
    }

    // Limita risultati
    const limit = Math.min(filters.limit || 100, 500);

    try {
      const response = await axios.get(`${API_URL}/audit/`, {
        params: {
          ...filters,
          limit,
        },
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching audit logs:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare log audit');
    }
  }

  /**
   * Ottiene statistiche audit
   */
  async getStats(since?: string): Promise<AuditStats> {
    if (since && !validateISODate(since)) {
      throw new Error('Data since non valida');
    }

    try {
      const response = await axios.get(`${API_URL}/audit/stats/`, {
        params: since ? { since } : undefined,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching audit stats:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare statistiche');
    }
  }

  /**
   * Ottiene dettaglio singolo log
   */
  async getAuditLog(logId: number): Promise<AuditLog> {
    if (!Number.isInteger(logId) || logId < 1) {
      throw new Error('ID log non valido');
    }

    try {
      const response = await axios.get(`${API_URL}/audit/${logId}/`);
      return response.data;
    } catch (error: any) {
      console.error('Error fetching audit log:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare log');
    }
  }

  /**
   * Esporta log audit in formato JSON
   */
  async exportLogs(filters: AuditFilter = {}): Promise<Blob> {
    // Validazione filtri
    if (filters.username && !validateUsername(filters.username)) {
      throw new Error('Username non valido');
    }

    if (filters.since && !validateISODate(filters.since)) {
      throw new Error('Data since non valida');
    }

    if (filters.until && !validateISODate(filters.until)) {
      throw new Error('Data until non valida');
    }

    try {
      const response = await axios.get(`${API_URL}/audit/export/`, {
        params: filters,
        responseType: 'blob',
      });
      return response.data;
    } catch (error: any) {
      console.error('Error exporting logs:', error);
      throw new Error(error.response?.data?.error || 'Impossibile esportare log');
    }
  }

  /**
   * Ottiene azioni recenti per un utente
   */
  async getUserActions(username: string, limit: number = 20): Promise<AuditLog[]> {
    if (!validateUsername(username)) {
      throw new Error('Username non valido');
    }

    const safeLimit = Math.min(limit, 100);

    try {
      const response = await axios.get(`${API_URL}/audit/`, {
        params: {
          username,
          limit: safeLimit,
        },
      });
      return response.data.results;
    } catch (error: any) {
      console.error('Error fetching user actions:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare azioni utente');
    }
  }

  /**
   * Ottiene azioni per un target specifico
   */
  async getTargetActions(targetId: number, limit: number = 20): Promise<AuditLog[]> {
    if (!Number.isInteger(targetId) || targetId < 1) {
      throw new Error('ID target non valido');
    }

    const safeLimit = Math.min(limit, 100);

    try {
      const response = await axios.get(`${API_URL}/audit/`, {
        params: {
          target_id: targetId,
          limit: safeLimit,
        },
      });
      return response.data.results;
    } catch (error: any) {
      console.error('Error fetching target actions:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare azioni target');
    }
  }
}

export default new AuditService();
