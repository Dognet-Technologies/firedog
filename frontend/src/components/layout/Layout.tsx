/**
 * Professional Layout Component - Chronograf Style
 * Con Target Selector integrato nella navbar
 */
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTarget } from '../../contexts/TargetContext';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path?: string;
  subItems?: NavItem[];
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { logout, user } = useAuth();
  const { selectedTarget, targets, setSelectedTarget, loading: targetsLoading } = useTarget();
  const navigate = useNavigate();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedSections, setExpandedSections] = useState<string[]>(['dashboard']);
  const [showTargetDropdown, setShowTargetDropdown] = useState(false);

  const navigationItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: 'dashboard',
      path: '/dashboard',
    },
    {
      id: 'firewall',
      label: 'Gestione Firewall',
      icon: 'shield',
      subItems: [
        { id: 'firewall-rules', label: 'Regole Firewall', icon: 'list', path: '/firewall/rules' },
        { id: 'firewall-targets', label: 'Target Protetti', icon: 'target', path: '/targets' },
        { id: 'firewall-blocked', label: 'IP Bloccati', icon: 'block', path: '/firewall/blocked' },
        { id: 'firewall-whitelist', label: 'Whitelist', icon: 'check', path: '/firewall/whitelist' },
      ],
    },
    {
      id: 'monitoring',
      label: 'Monitoraggio',
      icon: 'activity',
      subItems: [
        { id: 'monitoring-threats', label: 'Threat Detection', icon: 'alert', path: '/threats' },
      ],
    },
    {
      id: 'discovery',
      label: 'Discovery',
      icon: 'radar',
      path: '/discovery',
    },
    {
      id: 'logs',
      label: 'Log',
      icon: 'file-text',
      subItems: [
        { id: 'logs-audit', label: 'Audit Logs', icon: 'book', path: '/audit' },
        { id: 'logs-firedog', label: 'System Logs', icon: 'terminal', path: '/logs' },
      ],
    },
    {
      id: 'settings',
      label: 'Impostazioni',
      icon: 'settings',
      subItems: [
        { id: 'settings-general', label: 'Generali', icon: 'sliders', path: '/settings/general' },
        { id: 'settings-integrity', label: 'File Integrity', icon: 'lock', path: '/integrity' },
        { id: 'settings-notifications', label: 'Notifiche', icon: 'bell', path: '/settings/notifications' },
        { id: 'settings-users', label: 'Utenti', icon: 'users', path: '/settings/users' },
      ],
    },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) =>
      prev.includes(sectionId)
        ? prev.filter((id) => id !== sectionId)
        : [...prev, sectionId]
    );
  };

  const isActive = (path?: string) => {
    if (!path) return false;
    return location.pathname === path || location.pathname.startsWith(path);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <span className="status-dot status-online" title="Online"></span>;
      case 'offline':
        return <span className="status-dot status-offline" title="Offline"></span>;
      case 'error':
        return <span className="status-dot status-error" title="Error"></span>;
      case 'installing':
        return <span className="status-dot status-installing" title="Installing"></span>;
      default:
        return <span className="status-dot status-pending" title="Pending"></span>;
    }
  };

  const renderIcon = (iconName: string) => {
    const icons: { [key: string]: JSX.Element } = {
      dashboard: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" />
          <rect x="14" y="3" width="7" height="7" />
          <rect x="14" y="14" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" />
        </svg>
      ),
      shield: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      ),
      activity: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
      radar: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          <line x1="12" y1="2" x2="12" y2="22" />
        </svg>
      ),
      'file-text': (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      ),
      settings: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v6m0 6v6M5.6 5.6l4.2 4.2m4.2 4.2l4.2 4.2M1 12h6m6 0h6M5.6 18.4l4.2-4.2m4.2-4.2l4.2-4.2" />
        </svg>
      ),
      list: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="8" y1="6" x2="21" y2="6" />
          <line x1="8" y1="12" x2="21" y2="12" />
          <line x1="8" y1="18" x2="21" y2="18" />
          <line x1="3" y1="6" x2="3.01" y2="6" />
          <line x1="3" y1="12" x2="3.01" y2="12" />
          <line x1="3" y1="18" x2="3.01" y2="18" />
        </svg>
      ),
      target: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="2" />
        </svg>
      ),
      block: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
        </svg>
      ),
      check: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ),
      alert: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
      book: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      ),
      terminal: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="4 17 10 11 4 5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
      ),
      sliders: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="4" y1="21" x2="4" y2="14" />
          <line x1="4" y1="10" x2="4" y2="3" />
          <line x1="12" y1="21" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12" y2="3" />
          <line x1="20" y1="21" x2="20" y2="16" />
          <line x1="20" y1="12" x2="20" y2="3" />
          <line x1="1" y1="14" x2="7" y2="14" />
          <line x1="9" y1="8" x2="15" y2="8" />
          <line x1="17" y1="16" x2="23" y2="16" />
        </svg>
      ),
      lock: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      ),
      bell: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
      ),
      users: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      ),
    };
    return icons[iconName] || icons.dashboard;
  };

  const renderNavItem = (item: NavItem, level: number = 0) => {
    const hasSubItems = item.subItems && item.subItems.length > 0;
    const isExpanded = expandedSections.includes(item.id);
    const active = isActive(item.path);

    if (hasSubItems) {
      return (
        <div key={item.id} className="nav-section">
          <button
            className={`nav-item nav-item-parent ${isExpanded ? 'expanded' : ''}`}
            onClick={() => toggleSection(item.id)}
          >
            <div className="nav-item-content">
              <span className="nav-icon">{renderIcon(item.icon)}</span>
              {!isCollapsed && <span className="nav-label">{item.label}</span>}
            </div>
            {!isCollapsed && (
              <svg
                className="nav-arrow"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            )}
          </button>
          {isExpanded && !isCollapsed && item.subItems && (
            <div className="nav-subitems">
              {item.subItems.map((subItem) => (
                <a
                  key={subItem.id}
                  href={subItem.path}
                  className={`nav-item nav-item-sub ${isActive(subItem.path) ? 'active' : ''}`}
                >
                  <span className="nav-icon">{renderIcon(subItem.icon)}</span>
                  <span className="nav-label">{subItem.label}</span>
                </a>
              ))}
            </div>
          )}
        </div>
      );
    }

    return (
      <a
        key={item.id}
        href={item.path}
        className={`nav-item ${active ? 'active' : ''}`}
      >
        <span className="nav-icon">{renderIcon(item.icon)}</span>
        {!isCollapsed && <span className="nav-label">{item.label}</span>}
      </a>
    );
  };

  return (
    <div className="layout">
      <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 8v8M8 14l4 4 4-4" />
            </svg>
            {!isCollapsed && <span className="logo-text">FireDog</span>}
          </div>
          <button
            className="btn-collapse"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? 'Espandi' : 'Comprimi'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points={isCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'} />
            </svg>
          </button>
        </div>

        {/* TARGET SELECTOR */}
        {!isCollapsed && (
          <div className="target-selector-container">
            <label className="target-selector-label">Target Selezionato:</label>
            <div className="target-selector">
              <button
                className="target-selector-button"
                onClick={() => setShowTargetDropdown(!showTargetDropdown)}
                disabled={targetsLoading}
              >
                {targetsLoading ? (
                  <span>Caricamento...</span>
                ) : selectedTarget ? (
                  <>
                    {getStatusIcon(selectedTarget.status)}
                    <span className="target-name">
                      {selectedTarget.hostname || selectedTarget.ip_address}
                    </span>
                    <svg className="dropdown-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </>
                ) : (
                  <span className="no-target">Seleziona target...</span>
                )}
              </button>

              {showTargetDropdown && (
                <>
                  <div 
                    className="dropdown-overlay" 
                    onClick={() => setShowTargetDropdown(false)}
                  />
                  <div className="target-dropdown">
                    {targets.length === 0 ? (
                      <div className="dropdown-empty">
                        <p>Nessun target online</p>
                        <a href="/targets" className="dropdown-link">
                          Gestisci targets →
                        </a>
                      </div>
                    ) : (
                      targets.map((target) => (
                        <button
                          key={target.id}
                          className={`target-dropdown-item ${
                            selectedTarget?.id === target.id ? 'selected' : ''
                          }`}
                          onClick={() => {
                            setSelectedTarget(target);
                            setShowTargetDropdown(false);
                          }}
                        >
                          {getStatusIcon(target.status)}
                          <div className="target-info">
                            <span className="target-hostname">
                              {target.hostname || target.ip_address}
                            </span>
                            <span className="target-ip">{target.ip_address}</span>
                          </div>
                          {selectedTarget?.id === target.id && (
                            <svg className="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        <nav className="nav">
          {navigationItems.map((item) => renderNavItem(item))}
        </nav>

        <div className="sidebar-footer">
          <div className="status-indicator">
            <span className="status-dot status-online"></span>
            {!isCollapsed && <span className="status-text">Sistema Attivo</span>}
          </div>
          {!isCollapsed && (
            <>
              <div className="user-info">
                <div className="user-avatar">
                  {(user?.username || 'Admin').charAt(0).toUpperCase()}
                </div>
                <span className="user-name">{user?.username || 'Admin'}</span>
              </div>
              <button onClick={handleLogout} className="btn-logout">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Logout
              </button>
            </>
          )}
        </div>
      </aside>

      <main className="main-content">
        <div className="content-wrapper">{children}</div>
      </main>
    </div>
  );
};

export default Layout;
