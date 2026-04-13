/**
 * Main App Component with Routing
 */
import React from 'react';
import './App.css';
import './contexts/NotificationContext.css';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { NotificationProvider } from './contexts/NotificationContext';
import { TargetProvider } from './contexts/TargetContext';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Targets from './pages/Targets';
import TargetDetail from './pages/TargetDetail';
import Groups from './pages/Groups';
import GroupDetail from './pages/GroupDetail';
import Firewall from './pages/Firewall';
import Threats from './pages/Threats';
import Discovery from './pages/Discovery';
import Monitoring from './pages/Monitoring';
import Audit from './pages/Audit';
import Integrity from './pages/Integrity';
import LogsPage from './pages/LogsPage';
import Settings from './pages/Settings';

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
      <TargetProvider>
        <NotificationProvider>
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
                path="/targets/:id"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <TargetDetail />
                    </Layout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/groups"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Groups />
                    </Layout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/groups/:id"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <GroupDetail />
                    </Layout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/firewall"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Firewall />
                    </Layout>
                  </ProtectedRoute>
                }
              />
              {/* Legacy firewall sub-routes — redirect to tabbed Firewall page */}
              <Route path="/firewall/rules" element={<Navigate to="/firewall" replace />} />
              <Route path="/firewall/blocked" element={<Navigate to="/firewall" replace />} />
              <Route path="/firewall/whitelist" element={<Navigate to="/firewall" replace />} />
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
                path="/discovery"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Discovery />
                    </Layout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/monitoring"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Monitoring />
                    </Layout>
                  </ProtectedRoute>
                }
              />
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
                path="/integrity"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <Integrity />
                    </Layout>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/logs"
                element={
                  <ProtectedRoute>
                    <Layout>
                      <LogsPage />
                    </Layout>
                  </ProtectedRoute>
                }
              />
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

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Router>
        </NotificationProvider>
      </TargetProvider>
    </AuthProvider>
  );
}

export default App;
