/**
 * TypeScript Types per FireDog Frontend
 */

// ========== API Response Types ==========

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ========== Target Types ==========

export interface TargetGroupInfo {
  id: number;
  name: string;
  color: string;
  icon?: string;
}

export interface Target {
  id: number;
  ip_address: string;
  hostname: string;
  description: string;
  status: 'unpaired' | 'pairing' | 'pending' | 'installing' | 'online' | 'offline' | 'error';
  firedog_version: string;
  ssh_port: number;
  ssh_user: string;
  last_seen: string | null;
  last_fetch: string | null;
  error_message: string;
  created_at: string;
  updated_at: string;
  connection_string: string;
  is_active: boolean;
  gruppo?: string | null;
  gruppo_custom?: string | null;
  gruppo_display?: string;
  target_groups?: TargetGroupInfo[];
}

export interface TargetCreate {
  ip_address: string;
  hostname?: string;
  mac_address?: string;
  description?: string;
  ssh_port?: number;
  ssh_user?: string;
  gruppo?: string;
  gruppo_custom?: string;
}

export interface TargetStatus {
  ip_address: string;
  hostname: string;
  status: string;
  firedog_version: string;
  last_seen: string | null;
  last_fetch: string | null;
  is_active: boolean;
  error_message: string;
  rules_count: number;
  threats_count: number;
}

// ========== Firewall Rule Types ==========

export interface FirewallRule {
  id: number;
  target: number;
  target_ip: string;
  chain: 'INPUT' | 'OUTPUT' | 'FORWARD';
  rule_number: number | null;
  protocol: 'tcp' | 'udp' | 'icmp' | 'all';
  port: number | null;
  source_ip: string | null;
  dest_ip: string | null;
  action: 'ACCEPT' | 'DROP' | 'REJECT';
  comment: string;
  is_custom: boolean;
  is_synced: boolean;
  created_at: string;
  updated_at: string;
  rule_description: string;
}

export interface FirewallRuleCreate {
  target: number;
  chain: 'INPUT' | 'OUTPUT' | 'FORWARD';
  protocol: 'tcp' | 'udp' | 'icmp' | 'all';
  port?: number;
  source_ip?: string;
  dest_ip?: string;
  action: 'ACCEPT' | 'DROP' | 'REJECT';
  comment?: string;
}

// ========== Threat Types ==========

export interface ThreatLog {
  id: number;
  target: number;
  target_ip: string;
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
  attack_description: string;
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
  }>;
  recent_threats: ThreatLog[];
}

// ========== Dashboard Types ==========

export interface Dashboard {
  id: number;
  user: number;
  name: string;
  description: string;
  is_default: boolean;
  is_public: boolean;
  layout_config: any;
  widgets: Widget[];
  widget_count: number;
  created_at: string;
  updated_at: string;
}

export interface Widget {
  id: number;
  dashboard: number;
  title: string;
  widget_type: 
    | 'threat_summary'
    | 'threat_chart'
    | 'target_status'
    | 'recent_threats'
    | 'top_attackers'
    | 'rule_count'
    | 'traffic_stats'
    | 'activity_timeline'
    | 'geo_map'
    | 'custom';
  config: any;
  grid_position: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  is_visible: boolean;
  refresh_interval: number;
  created_at: string;
  updated_at: string;
}

// ========== Discovery Types ==========

export interface DiscoveredHost {
  id: number;
  ip_address: string;
  mac_address: string;
  hostname: string;
  vendor: string;
  network: string;
  netmask: string;
  discovered_at: string;
  last_seen: string;
  scan_count: number;
  is_alive: boolean;
  is_imported: boolean;
  notes: string;
  display_name: string;
  is_recently_discovered: boolean;
  already_target: boolean;
}

export interface DiscoveryScanResult {
  task_id: string;
  message: string;
  status: 'running' | 'completed' | 'failed';
}

export interface DiscoveryScanStatus {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE';
  result?: {
    success: boolean;
    networks_scanned: string[];
    hosts_found: number;
    hosts_new: number;
    hosts_updated: number;
  };
}

export interface BulkImportResult {
  imported: number;
  skipped: number;
  errors: Array<{
    line: number;
    error: string;
    content: string;
  }>;
}

// ========== File Integrity Types ==========

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
  approved_by: number | null;
  approved_by_username: string;
  approved_at: string | null;
  change_notes: string;
  alert_sent: boolean;
  created_at: string;
  needs_attention: boolean;
}

// ========== Audit Log Types ==========

export interface AuditLog {
  id: number;
  user: number | null;
  username: string;
  action: string;
  action_display: string;
  description: string;
  old_values: any;
  new_values: any;
  ip_address: string ;
  user_agent: string;
  success: boolean;
  error_message: string;
  created_at: string;
  target_id: number | null;
  target_hostname: string | null;
  details: any;
  timestamp: string;
  action_description: string;
}

// // ========== Auth Types ==========

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

// ========== Chart Data Types ==========

export interface ChartDataPoint {
  name: string;
  value: number;
  [key: string]: any;
}

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
  [key: string]: any;
}

/**
 * TypeScript Types
 * AGGIUNGERE a frontend/src/types/index.ts
 */

// ==================== NOTIFICATION TYPES ====================

export interface NotificationConfig {
  id: number;
  email_enabled: boolean;
  email_recipients: string[];
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password?: string;
  smtp_use_tls: boolean;
  smtp_from_email: string;
  slack_enabled: boolean;
  slack_webhook_url: string;
  discord_enabled: boolean;
  discord_webhook_url: string;
  alert_on_critical_threat: boolean;
  alert_on_high_threat: boolean;
  alert_on_target_offline: boolean;
  target_offline_threshold_minutes: number;
  alert_on_ssh_error: boolean;
  alert_on_install_success: boolean;
  alert_on_install_failed: boolean;
  cooldown_minutes: number;
  updated_at: string;
  updated_by: number | null;
  updated_by_username: string | null;
}

export interface NotificationLog {
  id: number;
  notification_type: 'email' | 'slack' | 'discord';
  notification_type_display: string;
  alert_type: string;
  alert_type_display: string;
  target: number | null;
  target_hostname: string | null;
  recipient: string;
  message: string;
  success: boolean;
  error_message: string;
  sent_at: string;
}

export interface SmtpInfo {
  title: string;
  description: string;
  steps: Array<{
    step: number;
    title: string;
    command: string;
    description: string;
  }>;
  common_configs: {
    [key: string]: {
      smtp_host: string;
      smtp_port: number;
      smtp_user: string;
      smtp_use_tls: boolean;
      description: string;
    };
  };
  troubleshooting: Array<{
    problem: string;
    solution: string;
  }>;
}

// ==================== USER TYPES ====================

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login: string;
}

export interface ChangeUsernameRequest {
  new_username: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}
