/**
 * Rules Service - Gestione regole firewall
 * Security: Input validation, sanitization, error handling
 */

import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// Validazione porta (1-65535)
const validatePort = (port: number | string): boolean => {
  const portNum = typeof port === 'string' ? parseInt(port, 10) : port;
  return !isNaN(portNum) && portNum >= 1 && portNum <= 65535;
};

// Validazione IP (basic regex)
const validateIP = (ip: string): boolean => {
  const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  return ipRegex.test(ip);
};

// Validazione CIDR
const validateCIDR = (cidr: string): boolean => {
  const cidrRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/([0-9]|[1-2][0-9]|3[0-2])$/;
  return cidrRegex.test(cidr);
};

// Sanitizzazione commento (rimuove caratteri pericolosi)
const sanitizeComment = (comment: string): string => {
  return comment
    .replace(/[<>'"]/g, '')
    .replace(/[;&|`$()]/g, '')
    .trim()
    .substring(0, 256);
};

// Validazione chain
const validateChain = (chain: string): boolean => {
  return ['INPUT', 'OUTPUT', 'FORWARD'].includes(chain.toUpperCase());
};

// Validazione protocol
const validateProtocol = (protocol: string): boolean => {
  return ['tcp', 'udp', 'icmp', 'all'].includes(protocol.toLowerCase());
};

export interface FirewallRule {
  id: number;
  target: number;
  chain: 'INPUT' | 'OUTPUT' | 'FORWARD';
  rule_number: number;
  protocol: string;
  port?: number;
  source_ip?: string;
  dest_ip?: string;
  action: 'ACCEPT' | 'DROP' | 'REJECT';
  comment?: string;
  packets?: number;
  bytes?: number;
  is_custom: boolean;
  is_synced: boolean;
  created_at: string;
  updated_at: string;
}

export interface RulesResponse {
  input_rules: FirewallRule[];
  output_rules: FirewallRule[];
  forward_rules?: FirewallRule[];
  total_rules: number;
  last_sync: string;
}

export interface AddRuleRequest {
  chain: 'INPUT' | 'OUTPUT';
  port: number;
  protocol?: 'tcp' | 'udp' | 'icmp';
  source_ip?: string;
  dest_ip?: string;
  comment?: string;
}

class RulesService {
  async getRules(targetId: number, refresh: boolean = false): Promise<RulesResponse> {
    try {
      const response = await axios.get(`${API_URL}/rules/`, {
        params: {
          target: targetId,
          refresh: refresh ? 'true' : undefined,
        },
      });
      return response.data;
    } catch (error: any) {
      console.error('Error fetching rules:', error);
      throw new Error(error.response?.data?.error || 'Impossibile recuperare le regole');
    }
  }

  async syncRules(targetId: number): Promise<{ message: string; synced_rules: number }> {
    try {
      const response = await axios.post(`${API_URL}/targets/${targetId}/sync-rules/`);
      return response.data;
    } catch (error: any) {
      console.error('Error syncing rules:', error);
      throw new Error(error.response?.data?.error || 'Impossibile sincronizzare le regole');
    }
  }

  async addRule(targetId: number, rule: AddRuleRequest): Promise<{ message: string; rule: FirewallRule }> {
    // Validazione input (OWASP)
    if (!validateChain(rule.chain)) {
      throw new Error('Chain non valida. Usare INPUT o OUTPUT');
    }

    if (!validatePort(rule.port)) {
      throw new Error('Porta non valida. Deve essere tra 1 e 65535');
    }

    if (rule.protocol && !validateProtocol(rule.protocol)) {
      throw new Error('Protocollo non valido');
    }

    if (rule.source_ip && !validateIP(rule.source_ip) && !validateCIDR(rule.source_ip)) {
      throw new Error('IP sorgente non valido');
    }

    if (rule.dest_ip && !validateIP(rule.dest_ip) && !validateCIDR(rule.dest_ip)) {
      throw new Error('IP destinazione non valido');
    }

    const sanitizedRule = {
      ...rule,
      comment: rule.comment ? sanitizeComment(rule.comment) : undefined,
      protocol: rule.protocol?.toLowerCase() || 'tcp',
    };

    try {
      const response = await axios.post(`${API_URL}/targets/${targetId}/add-rule/`, sanitizedRule);
      return response.data;
    } catch (error: any) {
      console.error('Error adding rule:', error);
      throw new Error(error.response?.data?.error || 'Impossibile aggiungere la regola');
    }
  }

  async removeRule(targetId: number, chain: string, ruleNumber: number): Promise<{ message: string }> {
    if (!validateChain(chain)) {
      throw new Error('Chain non valida');
    }

    if (!Number.isInteger(ruleNumber) || ruleNumber < 1) {
      throw new Error('Numero regola non valido');
    }

    try {
      const response = await axios.post(`${API_URL}/targets/${targetId}/remove-rule/`, {
        chain: chain.toUpperCase(),
        rule_number: ruleNumber,
      });
      return response.data;
    } catch (error: any) {
      console.error('Error removing rule:', error);
      throw new Error(error.response?.data?.error || 'Impossibile rimuovere la regola');
    }
  }
}

export default new RulesService();
