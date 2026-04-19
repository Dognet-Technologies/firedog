 /**
 * Main App Component with Routing
import Whitelist from './pages/Whitelist';
 */
import React from 'react';
import './App.css';
import './contexts/NotificationContext.css';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { NotificationProvider } from './contexts/NotificationContext';
import { TargetProvider } from './contexts/TargetContext';
import Layout from './components/layout/Layout';
import Discovery from './pages/Discovery';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Targets from './pages/Targets';
import Settings from './pages/Settings';
import Rules from './pages/FirewallRules';
import Threats from './pages/Threats';
import Audit from './pages/Audit';
import Integrity from './pages/Integrity';
import MonitoringTraffic from './pages/MonitoringTraffic';
import MonitoringPerformance from './pages/MonitoringPerformance';
import SystemLogs from './pages/SystemLogs';
import BlockedIPs from './pages/BlockedIPs';
import LogsPage from './pages/LogsPage';
import Whitelist from  './pages/Whitelist';



// Protected Route Component
interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

// Public Route Component (redirect to dashboard if already logged in)
interface PublicRouteProps {
  children: React.ReactNode;
}

const PublicRoute: React.FC<PublicRouteProps> = ({ children }) => {
  const token = localStorage.getItem('access_token');
  
  if (token) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <>{children}</>;
};

// Wrapper che applica TargetProvider solo alle route protette
const ProtectedWithTarget: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <TargetProvider>
    <NotificationProvider>
      {children}
    </NotificationProvider>
  </TargetProvider>
);

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>

          {/* Public Routes */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <Login />
              </PublicRoute>
            }
          />

          {/* Protected Routes — TargetProvider e NotificationProvider solo qui */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <ProtectedWithTarget>
                  <Layout>
                    <Navigate to="/dashboard" replace />
                  </Layout>
                </ProtectedWithTarget>
              </ProtectedRoute>
            }
          />
          <Route path="/discovery" element={<ProtectedRoute><ProtectedWithTarget><Layout><Discovery /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><ProtectedWithTarget><Layout><Dashboard /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/targets" element={<ProtectedRoute><ProtectedWithTarget><Layout><Targets /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/firewall/rules" element={<ProtectedRoute><ProtectedWithTarget><Layout><Rules /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/firewall/blocked" element={<ProtectedRoute><ProtectedWithTarget><Layout><BlockedIPs /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/firewall/whitelist" element={<ProtectedRoute><ProtectedWithTarget><Layout><Whitelist /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/logs" element={<ProtectedRoute><ProtectedWithTarget><Layout><LogsPage /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/audit" element={<ProtectedRoute><ProtectedWithTarget><Layout><Audit /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/threats" element={<ProtectedRoute><ProtectedWithTarget><Layout><Threats /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/integrity" element={<ProtectedRoute><ProtectedWithTarget><Layout><Integrity /></Layout></ProtectedWithTarget></ProtectedRoute>} />
          <Route path="/settings/*" element={<ProtectedRoute><ProtectedWithTarget><Layout><Settings /></Layout></ProtectedWithTarget></ProtectedRoute>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
