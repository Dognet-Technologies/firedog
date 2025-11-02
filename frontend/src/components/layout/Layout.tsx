/**
 * Main Layout Component
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">
          <h1>🔥 FireDog</h1>
        </div>
        
        <nav className="nav">
          <a href="/dashboard" className="nav-item">
            <span className="icon">📊</span>
            Dashboard
          </a>
          <a href="/targets" className="nav-item">
            <span className="icon">🎯</span>
            Targets
          </a>
          <a href="/rules" className="nav-item">
            <span className="icon">📋</span>
            Rules
          </a>
          <a href="/threats" className="nav-item">
            <span className="icon">⚠️</span>
            Threats
          </a>
          <a href="/discovery" className="nav-item">
            <span className="icon">🔍</span>
            Discovery
          </a>
          <a href="/integrity" className="nav-item">
            <span className="icon">🔒</span>
            Integrity
          </a>
          <a href="/audit" className="nav-item">
            <span className="icon">📝</span>
            Audit Logs
          </a>
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <span className="user-name">{user?.username || 'Admin'}</span>
          </div>
          <button onClick={handleLogout} className="btn-logout">
            Logout
          </button>
        </div>
      </aside>

      <main className="main-content">
        <div className="content-wrapper">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
