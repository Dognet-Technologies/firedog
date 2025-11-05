/**
 * Main App Component with Routing
 */
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/layout/Layout';
import Discovery from './pages/Discovery';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Targets from './pages/Targets';
import Settings from './pages/Settings';
import './App.css';

import Rules from './pages/Rules';
import Threats from './pages/Threats';
import Audit from './pages/Audit';
import Integrity from './pages/Integrity';
import AuditLogs from './pages/AuditLogs';
import FirewallLogs from './pages/FirewallLogs';
import MonitoringTraffic from './pages/MonitoringTraffic';
import MonitoringPerformance from './pages/MonitoringPerformance';
import SystemLogs from './pages/SystemLogs';
import Whitelist from './pages/Whitelist';
import BlockedIPs from './pages/BlockedIPs';

// Nelle routes:


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

          {/* Protected Routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout>
                  <Navigate to="/dashboard" replace />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/discovery"
            element={
              <ProtectedRoute>
                <Layout><Discovery /></Layout>
              </ProtectedRoute>
            }
          />
          
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Layout>
                  <Dashboard />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/targets"
            element={
              <ProtectedRoute>
                <Layout>
                  <Targets />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/logs/audit"
            element={
              <ProtectedRoute>
                <Layout>
                  <AuditLogs />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/logs/firewall"
            element={
              <ProtectedRoute>
                <Layout>
                  <AuditLogs />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/monitoring/traffic"
            element={
              <ProtectedRoute>
                <Layout>
                  <AuditLogs />
                </Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/monitoring/performance"
            element={
              <ProtectedRoute>
                <Layout>
                  <AuditLogs />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/logs/system"
            element={
              <ProtectedRoute>
                <Layout>
                  <AuditLogs />
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route 
            path="/rules" 
            element={
              <ProtectedRoute>
                <Layout>
                  <Rules />
                </Layout>
              </ProtectedRoute>
            }
            />
            <Route
              path="/firewall/blocked"
              element={
                <ProtectedRoute>
                  <Layout>
                    <BlockedIPs />
                  </Layout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/firewall/whitelist"
              element={
                <ProtectedRoute>
                  <Layout>
                    <Whitelist />
                  </Layout>
                </ProtectedRoute>
              }
            />

          {/* Monitoring Routes */}
{/*          <Route
            path="/threats"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>Threat Detection</h1>
                    <p>Pagina in costruzione - Rilevamento minacce</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />*/}
          <Route 
            path="/threats" 
            element={
              <ProtectedRoute>
                <Layout>
                  <Threats />
                </Layout>
              </ProtectedRoute>
            }
            />


          <Route
            path="/monitoring/traffic"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>Traffico Rete</h1>
                    <p>Pagina in costruzione - Monitoraggio traffico</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/monitoring/performance"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>Performance</h1>
                    <p>Pagina in costruzione - Monitoraggio performance</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Discovery Route */}
          <Route
            path="/discovery"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>Network Discovery</h1>
                    <p>Pagina in costruzione - Scansione rete</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Log Routes */}
{/*          <Route
            path="/audit"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>Audit Logs</h1>
                    <p>Pagina in costruzione - Log di audit</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />*/}
          <Route 
            path="/audit" 
            element={
              <ProtectedRoute>
                <Layout>
                  <Audit />
                </Layout>
              </ProtectedRoute>
            }
            />


          <Route
            path="/logs/system"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>System Logs</h1>
                    <p>Pagina in costruzione - Log di sistema</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />

          <Route
            path="/logs/firewall"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>Firewall Logs</h1>
                    <p>Pagina in costruzione - Log firewall</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Settings Routes */}
          <Route
            path="/settings/*"
            element={
              <ProtectedRoute>
                <Layout>
                  <Settings />
                </Layout>
              </ProtectedRoute>
            }
          />

{/*          <Route
            path="/integrity"
            element={
              <ProtectedRoute>
                <Layout>
                  <div className="page-placeholder">
                    <h1>File Integrity</h1>
                    <p>Pagina in costruzione - Monitoraggio integrità file</p>
                  </div>
                </Layout>
              </ProtectedRoute>
            }
          />*/}
          <Route 
            path="/integrity" 
            element={
              <ProtectedRoute>
                <Layout>
                  <Integrity />
                </Layout>
              </ProtectedRoute>
            }
            />


          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
