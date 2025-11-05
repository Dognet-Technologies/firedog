/**
 * Integrity Service - File Integrity Monitoring
 * Security: Path validation, hash verification, approval workflow
 */

import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// Validazione path (no path traversal)
const validatePath = (path: string): boolean => {
  // Previene path traversal attacks
  if (path.includes('..') || path.includes('~')) {
    return false;
  }
  
  // Deve iniziare con /
  if (!path.startsWith('/')) {
    return false;
  }
  
  // Lunghezza massima
  if (path.length > 512) {
    return false;
  }
  
  return true;
};

// Validazione hash SHA512 (128 caratteri esadecimali)
const validateSHA512 = (hash: string): boolean => {
  const sha512Regex = /^[a-f0-9]{128}$/i;
  return sha512Regex.test(hash);
};

// Sanitizzazione note
const sanitizeNotes = (notes: string): string => {
  return notes
    .replace(/[<>'"]/g, '')
    .trim()
    .substring(0, 1000);
};

export interface FileIntegrity {
  id: number;
  file_path: string;
  file_type: string;
  sha512_hash: string;
  previous_hash: string;
  file_size: number;
  file_permissions: string;
  file_owner: string;
  status: 'ok' | 'modified' | 'missing' | 'new';
  last_checked: string;
  last_modified: string | null;
  change_detected_at: string | null;
  is_change_approved: boolean;
  approved_by: string | null;
  approved_at: string | null;
  change_notes: string;
  alert_sent: boolean;
  created_at: string;
}

export interface IntegrityStats {
  total_files: number;
  ok_files: number;
  modified_files: number;
  missing_files: number;
  new_files: number;
  pending_approval: number;
  last_check: string;
}

export interface IntegrityFilter {
  status?: string;
  is_change_approved?: boolean;
  file_type?: string;
  limit?: number;
  offset?: number;
}

class IntegrityService {
  /**
   * Ottiene lista file monitorati
   */
  async getFiles(filters: IntegrityFilter = {}): Promise<{ count: number; results: FileIntegrity[] }> {
    // Validazione filtri
    if (filters.status && !['ok', 'modified', 'missing', 'new'].includes(filters.status)) {
      throw new Error('Status non valido');
    }

    const limit = Math.min(filters.limit || 50, 200);

    try {
      const response = await axios.get(`${API_URL}/integrity/`, {
        params: {
          ...filters,
          limit,
        },
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching integrity files:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare file monitorati');
    }
  }

  /**
   * Ottiene statistiche integrity
   */
  async getStats(): Promise<IntegrityStats> {
    try {
      const response = await axios.get(`${API_URL}/integrity/stats/`);
      return response.data;
    } catch (error: any) {
      console.error('Error fetching integrity stats:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare statistiche');
    }
  }

  /**
   * Ottiene dettaglio singolo file
   */
  async getFile(fileId: number): Promise<FileIntegrity> {
    if (!Number.isInteger(fileId) || fileId < 1) {
      throw new Error('ID file non valido');
    }

    try {
      const response = await axios.get(`${API_URL}/integrity/${fileId}/`);
      return response.data;
    } catch (error: any) {
      console.error('Error fetching file:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare file');
    }
  }

  /**
   * Esegue check integrità di tutti i file
   */
  async checkIntegrity(): Promise<{ message: string; checked_files: number; violations: number }> {
    try {
      const response = await axios.post(`${API_URL}/integrity/check/`);
      return response.data;
    } catch (error: any) {
      console.error('Error checking integrity:', error);
      throw new Error(error.response?.data?.error || 'Impossibile eseguire check');
    }
  }

  /**
   * Approva modifica a un file
   */
  async approveChange(fileId: number, notes?: string): Promise<{ message: string }> {
    if (!Number.isInteger(fileId) || fileId < 1) {
      throw new Error('ID file non valido');
    }

    const sanitizedNotes = notes ? sanitizeNotes(notes) : undefined;

    try {
      const response = await axios.post(`${API_URL}/integrity/${fileId}/approve/`, {
        notes: sanitizedNotes,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error approving change:', error);
      throw new Error(error.response?.data?.error || 'Impossibile approvare modifica');
    }
  }

  /**
   * Aggiunge un file al monitoraggio
   */
  async addFile(filePath: string): Promise<{ message: string; file: FileIntegrity }> {
    if (!validatePath(filePath)) {
      throw new Error('Path non valido o potenzialmente pericoloso');
    }

    try {
      const response = await axios.post(`${API_URL}/integrity/add/`, {
        file_path: filePath,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error adding file:', error);
      throw new Error(error.response?.data?.error || 'Impossibile aggiungere file');
    }
  }

  /**
   * Rimuove un file dal monitoraggio
   */
  async removeFile(fileId: number): Promise<{ message: string }> {
    if (!Number.isInteger(fileId) || fileId < 1) {
      throw new Error('ID file non valido');
    }

    try {
      const response = await axios.delete(`${API_URL}/integrity/${fileId}/`);
      return response.data;
    } catch (error: any) {
      console.error('Error removing file:', error);
      throw new Error(error.response?.data?.error || 'Impossibile rimuovere file');
    }
  }

  /**
   * Inizializza monitoring per i file critici
   */
  async initializeMonitoring(): Promise<{ message: string; initialized_files: number }> {
    try {
      const response = await axios.post(`${API_URL}/integrity/initialize/`);
      return response.data;
    } catch (error: any) {
      console.error('Error initializing monitoring:', error);
      throw new Error(error.response?.data?.error || 'Impossibile inizializzare monitoring');
    }
  }
}

export default new IntegrityService();
