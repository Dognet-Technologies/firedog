/**
 * API Service per comunicazione con Backend Django
 */
import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  Target,
  TargetCreate,
  TargetStatus,
  FirewallRule,
  FirewallRuleCreate,
  ThreatLog,
  ThreatStats,
  Dashboard,
  Widget,
  DiscoveredHost,
  DiscoveryScanResult,
  DiscoveryScanStatus,
  BulkImportResult,
  FileIntegrity,
  AuditLog,
  LoginCredentials,
  AuthTokens,
  PaginatedResponse,
} from '../types';


   export interface SystemSetting {
     id: number;
     key: string;
     value: any;
     category: 'general' | 'appearance' | 'notifications' | 'security' | 'monitoring';
     description: string;
     is_public: boolean;
     updated_at: string;
     updated_by?: number;
     updated_by_username?: string;
   }

    export interface SSHKey {
      id: number;
      name: string;
      key_type: 'ed25519' | 'rsa' | 'ecdsa';
      key_size?: number;
      public_key: string;
      fingerprint: string;
      scope: 'global' | 'group' | 'target';
      scope_value?: string;
      created_at: string;
      created_by?: number;
      created_by_username?: string;
      is_active: boolean;
      last_used_at?: string;
      associated_targets: number;
    }

    export interface SSHKeyCreateData {
      name: string;
      key_type: 'ed25519' | 'rsa' | 'ecdsa';
      key_size?: number;
      scope: 'global' | 'group' | 'target';
      scope_value?: string;
      passphrase?: string;
    }

    export interface SSHKeyImportData {
      name: string;
      public_key: string;
      private_key: string;
      scope: 'global' | 'group' | 'target';
      scope_value?: string;
    }

    export interface AgentAPIKey {
      id: number;
      key_hash: string;
      is_active: boolean;
      created_at: string;
      expires_at?: string;
      created_by?: number;
      created_by_username?: string;
      last_used_at?: string;
    }

    export interface AgentAPIKeyGenerateResponse {
      raw_key: string;
      warning: string;
      api_key: AgentAPIKey;
    }

    export interface DatabaseStats {
      total_size: string;
      connection_status: 'connected' | 'error';
      database_name: string;
      database_version: string;
      targets_count: number;
      rules_count: number;
      threats_count: number;
      audit_logs_count: number;
      statistics_count: number;
      discovered_hosts_count: number;
      tables_size: { [key: string]: string };
    }

    export interface DatabaseCleanupData {
      cleanup_type: 'audit_logs' | 'threat_logs' | 'statistics' | 'discovered_hosts' | 'all';
      retention_days: number;
      dry_run?: boolean;
    }

    export interface DatabaseCleanupResult {
      success: boolean;
      records_deleted: number;
      dry_run: boolean;
      message: string;
    }

    export interface DatabaseConnectionTest {
      status: 'connected' | 'error';
      message: string;
      latency_ms: number;
      database_name: string;
      database_version: string;
    }

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor per aggiungere token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor per gestire refresh token
    this.api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const refreshToken = localStorage.getItem('refresh_token');
            if (refreshToken) {
              const response = await axios.post(`${API_BASE_URL.replace('/api', '')}/api/token/refresh/`, {
                refresh: refreshToken,
              });

              const { access } = response.data;
              localStorage.setItem('access_token', access);

              originalRequest.headers.Authorization = `Bearer ${access}`;
              return this.api(originalRequest);
            }
          } catch (refreshError) {
            // Refresh fallito, logout
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // ========== Authentication ==========

  async login(credentials: LoginCredentials): Promise<AuthTokens> {
    const response = await axios.post(`${API_BASE_URL.replace('/api', '')}/api/token/`, credentials);
    return response.data;
  }

  async refreshToken(refresh: string): Promise<{ access: string }> {
    const response = await axios.post(`${API_BASE_URL.replace('/api', '')}/api/token/refresh/`, { refresh });
    return response.data;
  }

  // ========== Targets ==========

  async getTargets(): Promise<PaginatedResponse<Target>> {
    const response = await this.api.get('/targets/');
    return response.data;
  }

  async getTarget(id: number): Promise<Target> {
    const response = await this.api.get(`/targets/${id}/`);
    return response.data;
  }

  async createTarget(data: TargetCreate): Promise<Target> {
    const response = await this.api.post('/targets/', data);
    return response.data;
  }

  async startPairing(targetId: number): Promise<{ id: number; status: string; expires_at: string }> {
    const response = await this.api.post('/agent/pairing/start/', { target_id: targetId });
    return response.data;
  }

  async updateTarget(id: number, data: Partial<Target>): Promise<Target> {
    const response = await this.api.patch(`/targets/${id}/`, data);
    return response.data;
  }

  async deleteTarget(id: number): Promise<void> {
    try {
      const response = await this.api.delete(`/targets/${id}/`);
      
      // Log per debug
      console.log(`Target ${id} eliminato:`, response.data);
      
      // Verifica eliminazione
      if (response.status === 204 || response.status === 200) {
        console.log('✅ Target eliminato con successo dal server');
        
        // Opzionale: verifica che non esista più
        try {
          await this.api.get(`/targets/${id}/`);
          console.warn('⚠️ Target ancora presente dopo eliminazione!');
        } catch (e: any) {
          if (e.response?.status === 404) {
            console.log('✅ Verifica: Target non più presente');
          }
        }
      }
      
      return response.data;
    } catch (error: any) {
      console.error('❌ Errore eliminazione target:', error);
      throw error;
    }
  }

  async checkIPExists(ipAddress: string): Promise<{ exists: boolean; target?: any }> {
    try {
      const response = await this.api.get(`/targets/check-ip/?ip=${ipAddress}`);
      return response.data;
    } catch (error) {
      console.error('Errore verifica IP:', error);
      return { exists: false };
    }
  }

  async testConnection(id: number): Promise<any> {
    const response = await this.api.post(`/targets/${id}/test_connection/`);
    return response.data;
  }

  async installFiredog(id: number): Promise<any> {
    const response = await this.api.post(`/targets/${id}/install/`);
    return response.data;
  }

  async installTarget(targetId: number, forceReinstall: boolean = false): Promise<any> {
  const response = await this.api.post(`/targets/${targetId}/install/`);
  return response.data;
  }

  async uninstallFiredog(id: number): Promise<any> {
    const response = await this.api.post(`/targets/${id}/uninstall/`);
    return response.data;
  }

  async getTargetStatus(id: number): Promise<TargetStatus> {
    const response = await this.api.get(`/targets/${id}/status/`);
    return response.data;
  }

  // ========== Monitoring ==========

  async getHeartbeats(targetId: number, limit = 96): Promise<any[]> {
    const response = await this.api.get('/agent/heartbeats/', {
      params: { target_id: targetId, limit },
    });
    return response.data.results ?? response.data;
  }

  async getFirewallStats(targetId: number, limit = 96): Promise<any[]> {
    const response = await this.api.get('/firewall-stats/', {
      params: { target_id: targetId, limit },
    });
    return response.data.results ?? response.data;
  }

  // ========== Firewall Rules ==========

  async getRules(targetId?: number): Promise<PaginatedResponse<FirewallRule>> {
    const params = targetId ? { target: targetId } : {};
    const response = await this.api.get('/rules/', { params });
    return response.data;
  }

  async getRule(id: number): Promise<FirewallRule> {
    const response = await this.api.get(`/rules/${id}/`);
    return response.data;
  }

  async createRule(data: FirewallRuleCreate): Promise<FirewallRule> {
    const response = await this.api.post('/rules/', data);
    return response.data;
  }

  async updateRule(id: number, data: Partial<FirewallRule>): Promise<FirewallRule> {
    const response = await this.api.patch(`/rules/${id}/`, data);
    return response.data;
  }

  async deleteRule(id: number): Promise<void> {
    await this.api.delete(`/rules/${id}/`);
  }

  // ========== Threats ==========

  async getThreats(filters?: any): Promise<PaginatedResponse<ThreatLog>> {
    const response = await this.api.get('/threats/', { params: filters });
    return response.data;
  }

  async getThreat(id: number): Promise<ThreatLog> {
    const response = await this.api.get(`/threats/${id}/`);
    return response.data;
  }

  async getThreatStats(): Promise<ThreatStats> {
    const response = await this.api.get('/threats/stats/');
    return response.data;
  }

  async markThreatResolved(id: number): Promise<ThreatLog> {
    const response = await this.api.patch(`/threats/${id}/`, { is_resolved: true });
    return response.data;
  }

  async blockThreatIP(id: number): Promise<ThreatLog> {
    const response = await this.api.patch(`/threats/${id}/`, { is_blocked: true });
    return response.data;
  }

  // ========== Dashboards ==========

  async getDashboards(): Promise<PaginatedResponse<Dashboard>> {
    const response = await this.api.get('/dashboards/');
    return response.data;
  }

  async getDashboard(id: number): Promise<Dashboard> {
    const response = await this.api.get(`/dashboards/${id}/`);
    return response.data;
  }

  async createDashboard(data: Partial<Dashboard>): Promise<Dashboard> {
    const response = await this.api.post('/dashboards/', data);
    return response.data;
  }

  async updateDashboard(id: number, data: Partial<Dashboard>): Promise<Dashboard> {
    const response = await this.api.patch(`/dashboards/${id}/`, data);
    return response.data;
  }

  async deleteDashboard(id: number): Promise<void> {
    await this.api.delete(`/dashboards/${id}/`);
  }

  // ========== Widgets ==========

  async getWidgets(dashboardId?: number): Promise<PaginatedResponse<Widget>> {
    const params = dashboardId ? { dashboard: dashboardId } : {};
    const response = await this.api.get('/widgets/', { params });
    return response.data;
  }

  async createWidget(data: Partial<Widget>): Promise<Widget> {
    const response = await this.api.post('/widgets/', data);
    return response.data;
  }

  async updateWidget(id: number, data: Partial<Widget>): Promise<Widget> {
    const response = await this.api.patch(`/widgets/${id}/`, data);
    return response.data;
  }

  async deleteWidget(id: number): Promise<void> {
    await this.api.delete(`/widgets/${id}/`);
  }

  // ========== Discovery (NEW) ==========

  async startDiscoveryScan(): Promise<DiscoveryScanResult> {
    const response = await this.api.post('/discovery/start_scan/');
    return response.data;
  }

  async getDiscoveryScanStatus(taskId: string): Promise<DiscoveryScanStatus> {
    const response = await this.api.get(`/discovery/scan_status/?task_id=${taskId}`);
    return response.data;
  }

  async getDiscoveryResults(notImported: boolean = false): Promise<{ count: number; hosts: DiscoveredHost[] }> {
    const response = await this.api.get(`/discovery/get_results/?not_imported=${notImported}`);
    return response.data;
  }

  async getDiscoveredHosts(): Promise<PaginatedResponse<DiscoveredHost>> {
    const response = await this.api.get('/discovery/');
    return response.data;
  }

  async scanNetwork(): Promise<any> {
    const response = await this.api.post('/discovery/scan/');
    return response.data;
  }

  async bulkImportFromFile(file: File): Promise<BulkImportResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await this.api.post('/discovery/bulk_import/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    return response.data;
  }

  async importDiscoveredHost(
    hostId: number,
    data?: { hostname?: string; description?: string }
  ): Promise<{ success: boolean; target_id: number; message: string }> {
    const response = await this.api.post(`/discovery/${hostId}/import_to_target/`, data || {});
    return response.data;
  }

  async bulkImportDiscoveredHosts(hostIds: number[]): Promise<BulkImportResult> {
    const response = await this.api.post('/discovery/bulk_import_to_targets/', {
      host_ids: hostIds
    });
    return response.data;
  }

  async bulkDeleteDiscoveredHosts(hostIds: number[]): Promise<any> {
    const response = await this.api.post('/discovery/bulk_delete/', {
      host_ids: hostIds
    });
    return response.data;
  }

  // ========== File Integrity ==========

  async getFileIntegrity(): Promise<PaginatedResponse<FileIntegrity>> {
    const response = await this.api.get('/integrity/');
    return response.data;
  }

  async approveFileChange(id: number, notes: string): Promise<any> {
    const response = await this.api.post(`/integrity/${id}/approve/`, { notes });
    return response.data;
  }

  async getAuditLogs(filters?: any): Promise<PaginatedResponse<AuditLog>> {
    const response = await this.api.get('/audit/', { params: filters });
    return response.data;
  }

  // ============================================================================
    // GROUPS API (VERSIONE CORRETTA)
    // ============================================================================
  async getGroups() {
      const response = await this.api.get('/groups/');
      return response.data;
  }

  async getGroup(groupId: number) {
    const response = await this.api.get(`/groups/${groupId}/`);
    return response.data;
  }

  async createGroup(data: { name: string; description?: string; color?: string; icon?: string }) {
    const response = await this.api.post('/groups/', data);
    return response.data;
  }

  async deleteGroup(groupId: number) {
    await this.api.delete(`/groups/${groupId}/`);
  }

  async addTargetsToGroup(groupId: number, targetIds: number[]) {
     const response = await this.api.post(
       `/groups/${groupId}/add_targets/`,
       { target_ids: targetIds }
     );
     return response.data;
  }

  async removeTargetsFromGroup(groupId: number, targetIds: number[]) {
    await this.api.post(
      `/groups/${groupId}/remove_targets/`,
      { target_ids: targetIds }
    );
  }

  async getAvailableTargetsForGroup(groupId: number) {
    const response = await this.api.get(
      `/groups/${groupId}/available_targets/`
    );
    return response.data;
  }

  async getGroupRules(groupId: number): Promise<{ count: number; results: FirewallRule[] }> {
    const response = await this.api.get(`/groups/${groupId}/rules/`);
    return response.data;
  }

  async addGroupRule(
    groupId: number,
    data: { chain: string; protocol: string; port?: number | null; source_ip?: string | null; dest_ip?: string | null; action: string; comment?: string }
  ): Promise<{ group: number; rules: { target_id: number; rule_id: number; dispatched: boolean }[]; dispatch_errors: Record<string, string> }> {
    const response = await this.api.post(`/groups/${groupId}/add-rule/`, data);
    return response.data;
  }

  async removeGroupRule(groupId: number, ruleId: number): Promise<{ removed: number[]; dispatch_errors: Record<string, string> }> {
    const response = await this.api.post(`/groups/${groupId}/remove-rule/${ruleId}/`);
    return response.data;
  }

  async getGroupOutOfSync(groupId: number): Promise<{
    group_id: number;
    canonical_total: number;
    out_of_sync_count: number;
    members: {
      target_id: number;
      target_label: string;
      in_sync: boolean;
      canonical_total: number;
      present_count: number;
      missing_count: number;
      missing_signatures: { chain: string; action: string; protocol: string; port: number | null; source_ip: string | null; dest_ip: string | null; comment: string }[];
      individual_rules_count: number;
    }[];
  }> {
    const response = await this.api.get(`/groups/${groupId}/out-of-sync/`);
    return response.data;
  }

  async applyGroupRulesToTarget(
    groupId: number,
    targetId: number,
    body: { overwrite: boolean; backup: boolean },
  ): Promise<{
    group_id: number;
    target_id: number;
    applied: { rule_id: number; dispatched: boolean }[];
    removed_individual: number[];
    dispatch_errors: Record<string, string>;
  }> {
    const response = await this.api.post(`/groups/${groupId}/apply-to-target/${targetId}/`, body);
    return response.data;
  }

  async syncTargetRules(targetId: number): Promise<{ command_id: string; status: string }> {
    const response = await this.api.post(`/targets/${targetId}/sync-rules/`);
    return response.data;
  }

  async checkSystemUpdate(): Promise<{ ok: boolean; error?: string; branch?: string; installed?: string; available?: string; commits_behind?: number; changelog?: string[]; up_to_date?: boolean }> {
    const response = await this.api.get('/system/update/check/');
    return response.data;
  }

  async installSystemUpdate(): Promise<{ ok: boolean; exit_code?: number; stdout?: string; stderr?: string; error?: string }> {
    // L'install può durare anche 1-2 minuti (npm ci + build + migrate + restart).
    // Aumento timeout default di axios per evitare di abortire prematuramente.
    const response = await this.api.post('/system/update/install/', undefined, { timeout: 10 * 60 * 1000 });
    return response.data;
  }

  async getDashboardFleetTraffic(hours = 24): Promise<{
    hours: number;
    series: { time: string; in: number; out: number; timestamp: string }[];
  }> {
    const response = await this.api.get('/dashboard/fleet-traffic/', { params: { hours } });
    return response.data;
  }

  async getDashboardGeo(targetId?: number): Promise<{
    total_flows: number;
    with_country: number;
    countries: { country_code: string; country_name: string; flows: number; times_seen: number; pct: number }[];
  }> {
    const response = await this.api.get('/dashboard/geo/', { params: targetId ? { target_id: targetId } : {} });
    return response.data;
  }

  // Whitelist methods
  async getWhitelistByTarget(targetId: number) {
    const response = await this.api.get(`/whitelist/by_target/?target_id=${targetId}`);
    return response.data;
  }

  async createWhitelistEntry(data: any) {
    const response = await this.api.post('/whitelist/', data);
    return response.data;
  }

  async deleteWhitelistEntry(id: number) {
    const response = await this.api.delete(`/whitelist/${id}/`);
    return response.data;
  }
    // Blocked IPs methods
  async getBlockedIPsByTarget(targetId: number) {
    const response = await this.api.get(`/blocked-ips/by_target/?target_id=${targetId}`);
    return response.data;
  }

  async createBlockedIP(data: any) {
    const response = await this.api.post('/blocked-ips/', data);
    return response.data;
  }

  async unblockIP(id: number) {
    const response = await this.api.post(`/blocked-ips/${id}/unblock/`);
    return response.data;
  }

  async getSettings(category?: string): Promise<SystemSetting[]> {
    const params = category ? { category } : {};
    const response = await this.api.get('/settings/', { params });
    return response.data.results || response.data;
  }

  async getSetting(id: number): Promise<SystemSetting> {
    const response = await this.api.get(`/settings/${id}/`);
    return response.data;
  }

  async createSetting(data: Partial<SystemSetting>): Promise<SystemSetting> {
    const response = await this.api.post('/settings/', data);
    return response.data;
  }

  async updateSetting(id: number, data: Partial<SystemSetting>): Promise<SystemSetting> {
    const response = await this.api.patch(`/settings/${id}/`, data);
    return response.data;
  }

  async deleteSetting(id: number): Promise<void> {
    await this.api.delete(`/settings/${id}/`);
  }

  async bulkUpdateSettings(settings: { [key: string]: any }, category?: string): Promise<any> {
    const response = await this.api.post('/settings/bulk_update/', {
      settings,
      category,
    });
    return response.data;
  }

  async resetSettings(category?: string): Promise<any> {
    const response = await this.api.post('/settings/reset/', {
      category,
    });
    return response.data;
  }

    // ========== SSH Keys ==========

  async getSSHKeys(scope?: string): Promise<SSHKey[]> {
    const params = scope ? { scope } : {};
    const response = await this.api.get('/settings/ssh-keys/', { params });
    return response.data.results || response.data;
  }

  async getSSHKey(id: number): Promise<SSHKey> {
    const response = await this.api.get(`/settings/ssh-keys/${id}/`);
    return response.data;
  }

  async generateSSHKey(data: SSHKeyCreateData): Promise<SSHKey> {
    const response = await this.api.post('/settings/ssh-keys/generate/', data);
    return response.data;
  }

  async importSSHKey(data: SSHKeyImportData): Promise<SSHKey> {
    const response = await this.api.post('/settings/ssh-keys/import_key/', data);
    return response.data;
  }

  async deleteSSHKey(id: number): Promise<void> {
    await this.api.delete(`/settings/ssh-keys/${id}/`);
  }

  async downloadSSHKeyPublic(id: number): Promise<Blob> {
    const response = await this.api.get(`/settings/ssh-keys/${id}/download/`, {
      responseType: 'blob',
    });
    return response.data;
  }

    // ========== Agent API Keys ==========

  async getAgentAPIKeys(): Promise<AgentAPIKey[]> {
    const response = await this.api.get('/agent/api-keys/');
    return response.data.results || response.data;
  }

  async getAgentAPIKey(id: number): Promise<AgentAPIKey> {
    const response = await this.api.get(`/agent/api-keys/${id}/`);
    return response.data;
  }

  async generateAgentAPIKey(): Promise<AgentAPIKeyGenerateResponse> {
    const response = await this.api.post('/agent/api-keys/generate/');
    return response.data;
  }

  async deleteAgentAPIKey(id: number): Promise<void> {
    await this.api.delete(`/agent/api-keys/${id}/`);
  }

  async activateAgentAPIKey(id: number): Promise<AgentAPIKey> {
    const response = await this.api.post(`/agent/api-keys/${id}/activate/`);
    return response.data;
  }

  async deactivateAgentAPIKey(id: number): Promise<AgentAPIKey> {
    const response = await this.api.post(`/agent/api-keys/${id}/deactivate/`);
    return response.data;
  }

  async retrieveAgentAPIKey(id: number, password: string): Promise<{ raw_key: string; key_id: number }> {
    const response = await this.api.post(`/agent/api-keys/${id}/retrieve_key/`, { password });
    return response.data;
  }

  // ========== Agent Groups ==========

  async getAgentGroups(): Promise<any> {
    const response = await this.api.get('/agent/groups/');
    return response.data;
  }

  async sendRuleToGroup(group: string, action: string, payload: any): Promise<any> {
    const response = await this.api.post('/agent/commands/send_to_group/', {
      group,
      action,
      payload
    });
    return response.data;
  }

    // ========== Database Management ==========

  async getDatabaseStats(): Promise<DatabaseStats> {
    const response = await this.api.get('/settings/database/stats/');
    return response.data;
  }

  async testDatabaseConnection(): Promise<DatabaseConnectionTest> {
    const response = await this.api.post('/settings/database/test_connection/');
    return response.data;
  }

  async cleanupDatabase(data: DatabaseCleanupData): Promise<DatabaseCleanupResult> {
    const response = await this.api.post('/settings/database/cleanup/', data);
    return response.data;
  }

  async getDatabaseCleanupLogs(): Promise<any[]> {
    const response = await this.api.get('/settings/database/cleanup_logs/');
    return response.data;
  }

  // CORREZIONE PER I NUOVI METODI
// Sostituisci dalla riga 620 alla fine del file api.ts

  // ==================== NOTIFICATION API ====================

  /**
   * Ottieni configurazione notifiche
   */
  async getNotificationConfig(): Promise<any> {
    const response = await this.api.get('/settings/notifications/config/');
    return response.data;
  }

  /**
   * Aggiorna configurazione notifiche
   */
  async updateNotificationConfig(config: any): Promise<any> {
    const response = await this.api.put('/settings/notifications/config/', config);
    return response.data;
  }

  /**
   * Test notifica (email/slack/discord)
   */
  async testNotification(data: {
    notification_type: 'email' | 'slack' | 'discord';
    test_recipient?: string;
  }): Promise<any> {
    const response = await this.api.post('/settings/notifications/test/', data);
    return response.data;
  }

  /**
   * Ottieni log notifiche
   */
  async getNotificationLogs(limit: number = 50): Promise<any> {
    const response = await this.api.get(`/settings/notifications/logs/?limit=${limit}`);
    return response.data;
  }

  /**
   * Ottieni info configurazione SMTP
   */
  async getSmtpInfo(): Promise<any> {
    const response = await this.api.get('/settings/notifications/smtp-info/');
    return response.data;
  }

  // ==================== USER MANAGEMENT API ====================

  /**
   * Ottieni profilo utente corrente
   */
  async getUserProfile(): Promise<any> {
    const response = await this.api.get('/settings/user/profile/');
    return response.data;
  }

  /**
   * Cambia username
   */
  async changeUsername(newUsername: string): Promise<any> {
    const response = await this.api.put('/settings/user/change-username/', {
      new_username: newUsername
    });
    return response.data;
  }

  /**
   * Cambia password
   */
  async changePassword(data: {
    current_password: string;
    new_password: string;
    confirm_password: string;
  }): Promise<any> {
    const response = await this.api.put('/settings/user/change-password/', data);
    return response.data;
  }
}

export default new ApiService();

