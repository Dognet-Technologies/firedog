import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Targets from './pages/Targets';
import './App.css';

const PrivateRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  return isAuthenticated ? children : <Navigate to="/login" />;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/dashboard" />} />
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Layout><Dashboard /></Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/targets"
        element={
          <PrivateRoute>
            <Layout><Targets /></Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/rules"
        element={
          <PrivateRoute>
            <Layout><div>Rules page - Coming soon</div></Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/threats"
        element={
          <PrivateRoute>
            <Layout><div>Threats page - Coming soon</div></Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/discovery"
        element={
          <PrivateRoute>
            <Layout><div>Discovery page - Coming soon</div></Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/integrity"
        element={
          <PrivateRoute>
            <Layout><div>Integrity page - Coming soon</div></Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/audit"
        element={
          <PrivateRoute>
            <Layout><div>Audit page - Coming soon</div></Layout>
          </PrivateRoute>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}

export default App;
