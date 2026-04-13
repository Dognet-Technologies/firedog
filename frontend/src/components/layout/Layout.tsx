/**
 * Layout Component — new sidebar + header bar design
 * Flat navigation, no sub-items, collapsible sidebar
 */
import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
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
  path: string;
}

const mainNavItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', path: '/dashboard' },
  { id: 'targets', label: 'Targets', icon: 'server', path: '/targets' },
  { id: 'groups', label: 'Groups', icon: 'layers', path: '/groups' },
  { id: 'firewall', label: 'Firewall', icon: 'shield', path: '/firewall' },
  { id: 'threats', label: 'Threats', icon: 'alert', path: '/threats' },
  { id: 'discovery', label: 'Discovery', icon: 'radar', path: '/discovery' },
  { id: 'monitoring', label: 'Monitoring', icon: 'activity', path: '/monitoring' },
  { id: 'logs', label: 'Logs', icon: 'file-text', path: '/logs' },
];

const settingsNavItem: NavItem = {
  id: 'settings',
  label: 'Settings',
  icon: 'settings',
  path: '/settings/general',
};

const getPageTitle = (pathname: string): string => {
  if (pathname.startsWith('/dashboard')) return 'Dashboard';
  if (pathname.startsWith('/targets/') && pathname !== '/targets') return 'Target Detail';
  if (pathname === '/targets') return 'Targets';
  if (pathname.startsWith('/groups/') && pathname !== '/groups') return 'Group Detail';
  if (pathname === '/groups') return 'Groups';
  if (pathname.startsWith('/firewall')) return 'Firewall';
  if (pathname.startsWith('/threats')) return 'Threats';
  if (pathname.startsWith('/discovery')) return 'Discovery';
  if (pathname.startsWith('/monitoring')) return 'Monitoring';
  if (pathname.startsWith('/logs')) return 'Logs';
  if (pathname.startsWith('/settings')) return 'Settings';
  return 'FireDog';
};

const renderIcon = (iconName: string): React.ReactElement => {
  const icons: Record<string, React.ReactElement> = {
    dashboard: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
    server: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="2" y="3" width="20" height="7" rx="1" />
        <rect x="2" y="14" width="20" height="7" rx="1" />
        <line x1="6" y1="7" x2="6.01" y2="7" />
        <line x1="6" y1="18" x2="6.01" y2="18" />
      </svg>
    ),
    layers: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polygon points="12 2 2 7 12 12 22 7 12 2" />
        <polyline points="2 17 12 22 22 17" />
        <polyline points="2 12 12 17 22 12" />
      </svg>
    ),
    shield: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
    alert: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
    radar: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        <line x1="12" y1="2" x2="12" y2="22" />
      </svg>
    ),
    activity: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
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
    bell: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
    logout: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <polyline points="16 17 21 12 16 7" />
        <line x1="21" y1="12" x2="9" y2="12" />
      </svg>
    ),
    chevron: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    ),
  };
  return icons[iconName] || icons.dashboard;
};

const getStatusClass = (status: string): string => {
  switch (status) {
    case 'online': return 'status-online';
    case 'offline': return 'status-offline';
    case 'error': return 'status-error';
    case 'installing': return 'status-installing';
    default: return 'status-pending';
  }
};

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { logout, user } = useAuth();
  const { selectedTarget, targets, setSelectedTarget, loading: targetsLoading } = useTarget();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showTargetDropdown, setShowTargetDropdown] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const pageTitle = getPageTitle(location.pathname);

  // Close user menu on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const isActive = (path: string): boolean => {
    if (path === '/dashboard') return location.pathname === '/dashboard';
    if (path === '/targets') return location.pathname === '/targets' || (location.pathname.startsWith('/targets/'));
    if (path === '/groups') return location.pathname === '/groups' || (location.pathname.startsWith('/groups/'));
    if (path === '/settings/general') return location.pathname.startsWith('/settings');
    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  const renderNavItem = (item: NavItem) => {
    const active = isActive(item.path);
    return (
      <Link
        key={item.id}
        to={item.path}
        className={`nav-item${active ? ' active' : ''}`}
        title={isCollapsed ? item.label : undefined}
      >
        <span className="nav-icon">{renderIcon(item.icon)}</span>
        {!isCollapsed && <span className="nav-label">{item.label}</span>}
      </Link>
    );
  };

  return (
    <div className="layout">
      {/* ===== SIDEBAR ===== */}
      <aside className={`sidebar${isCollapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 8v8M8 14l4 4 4-4" />
            </svg>
            {!isCollapsed && <span className="logo-text">FireDog</span>}
          </div>
          <button
            className="btn-collapse"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points={isCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'} />
            </svg>
          </button>
        </div>

        <nav className="nav">
          {mainNavItems.map(renderNavItem)}

          <div className="nav-separator" />

          {renderNavItem(settingsNavItem)}
        </nav>

        {/* Version footer */}
        <div className="sidebar-version">
          {!isCollapsed && <span className="version-text">v2.0.0</span>}
        </div>
      </aside>

      {/* ===== RIGHT PANEL ===== */}
      <div className="layout-right">
        {/* ===== HEADER BAR ===== */}
        <header className="header-bar">
          {/* Left: breadcrumb */}
          <div className="header-left">
            <span className="breadcrumb-title">{pageTitle}</span>
          </div>

          {/* Center: target selector */}
          <div className="header-center">
            <div className="target-selector">
              <button
                className="target-selector-btn"
                onClick={() => setShowTargetDropdown(!showTargetDropdown)}
                disabled={targetsLoading}
              >
                {targetsLoading ? (
                  <span className="target-selector-text">Loading...</span>
                ) : selectedTarget ? (
                  <>
                    <span className={`status-dot ${getStatusClass(selectedTarget.status)}`} />
                    <span className="target-selector-text">
                      {selectedTarget.hostname || selectedTarget.ip_address}
                    </span>
                  </>
                ) : (
                  <span className="target-selector-empty">Select target...</span>
                )}
                <span className="target-selector-arrow">{renderIcon('chevron')}</span>
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
                        <p>No targets online</p>
                        <Link
                          to="/targets"
                          className="dropdown-link"
                          onClick={() => setShowTargetDropdown(false)}
                        >
                          Manage targets →
                        </Link>
                      </div>
                    ) : (
                      targets.map((target) => (
                        <button
                          key={target.id}
                          className={`target-dropdown-item${selectedTarget?.id === target.id ? ' selected' : ''}`}
                          onClick={() => {
                            setSelectedTarget(target);
                            setShowTargetDropdown(false);
                          }}
                        >
                          <span className={`status-dot ${getStatusClass(target.status)}`} />
                          <div className="target-dropdown-info">
                            <span className="target-dropdown-name">
                              {target.hostname || target.ip_address}
                            </span>
                            <span className="target-dropdown-ip">{target.ip_address}</span>
                          </div>
                          {selectedTarget?.id === target.id && (
                            <svg className="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
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

          {/* Right: bell + user avatar */}
          <div className="header-right">
            <button className="header-icon-btn" title="Notifications">
              {renderIcon('bell')}
            </button>

            <div className="user-menu" ref={userMenuRef}>
              <button
                className="user-avatar-btn"
                onClick={() => setShowUserMenu(!showUserMenu)}
                title={user?.username || 'User'}
              >
                {(user?.username || 'A').charAt(0).toUpperCase()}
              </button>

              {showUserMenu && (
                <div className="user-menu-dropdown">
                  <div className="user-menu-header">
                    <div className="user-menu-avatar">
                      {(user?.username || 'A').charAt(0).toUpperCase()}
                    </div>
                    <div className="user-menu-info">
                      <span className="user-menu-name">{user?.username || 'Admin'}</span>
                      <span className="user-menu-role">Administrator</span>
                    </div>
                  </div>
                  <div className="user-menu-divider" />
                  <Link
                    to="/settings/general"
                    className="user-menu-item"
                    onClick={() => setShowUserMenu(false)}
                  >
                    {renderIcon('settings')}
                    <span>Settings</span>
                  </Link>
                  <button className="user-menu-item user-menu-logout" onClick={handleLogout}>
                    {renderIcon('logout')}
                    <span>Logout</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* ===== MAIN CONTENT ===== */}
        <main className="main-content">
          <div className="content-wrapper">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;
