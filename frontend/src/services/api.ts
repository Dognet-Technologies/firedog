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

  async updateTarget(id: number, data: Partial<Target>): Promise<Target> {
    const response = await this.api.patch(`/targets/${id}/`, data);
    return response.data;
  }

  async deleteTarget(id: number): Promise<void> {
    await this.api.delete(`/targets/${id}/`);
  }

  async testConnection(id: number): Promise<any> {
    const response = await this.api.post(`/targets/${id}/test_connection/`);
    return response.data;
  }

  async installFiredog(id: number): Promise<any> {
    const response = await this.api.post(`/targets/${id}/install/`);
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

  // ========== File Integrity ==========

  async getFileIntegrity(): Promise<PaginatedResponse<FileIntegrity>> {
    const response = await this.api.get('/integrity/');
    return response.data;
  }

  async approveFileChange(id: number, notes: string): Promise<any> {
    const response = await this.api.post(`/integrity/${id}/approve/`, { notes });
    return response.data;
  }

  // ========== Audit Logs ==========

  async getAuditLogs(): Promise<PaginatedResponse<AuditLog>> {
    const response = await this.api.get('/audit/');
    return response.data;
  }
}

export default new ApiService();