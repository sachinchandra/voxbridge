import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Agents from './pages/Agents';
import AgentEditor from './pages/AgentEditor';
import Calls from './pages/Calls';
import CallDetail from './pages/CallDetail';
import Analytics from './pages/Analytics';
import ApiKeys from './pages/ApiKeys';
import Usage from './pages/Usage';
import Billing from './pages/Billing';
import PhoneNumbers from './pages/PhoneNumbers';
import KnowledgeBases from './pages/KnowledgeBases';
import QualityAssurance from './pages/QualityAssurance';
import Playground from './pages/Playground';
import FlowBuilder from './pages/FlowBuilder';
import Alerts from './pages/Alerts';
import QuickStart from './pages/QuickStart';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0f0a1e] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/signup" element={<PublicRoute><Signup /></PublicRoute>} />

          {/* Protected routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="agents" element={<Agents />} />
            <Route path="agents/:agentId" element={<AgentEditor />} />
            <Route path="calls" element={<Calls />} />
            <Route path="calls/:callId" element={<CallDetail />} />
            <Route path="phone-numbers" element={<PhoneNumbers />} />
            <Route path="knowledge-bases" element={<KnowledgeBases />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="qa" element={<QualityAssurance />} />
            <Route path="playground" element={<Playground />} />
            <Route path="flows" element={<FlowBuilder />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="quickstart" element={<QuickStart />} />
            <Route path="keys" element={<ApiKeys />} />
            <Route path="usage" element={<Usage />} />
            <Route path="billing" element={<Billing />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
