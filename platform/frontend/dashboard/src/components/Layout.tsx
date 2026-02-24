import React from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useWS } from '../context/WebSocketContext';

const navItems = [
  { path: '/dashboard', label: 'Overview', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6', section: 'main' },
  { path: '/dashboard/live', label: 'Live Monitor', icon: 'M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728M9.172 15.828a5 5 0 010-7.072m5.656 0a5 5 0 010 7.072M13 12a1 1 0 11-2 0 1 1 0 012 0z', section: 'main' },
  { path: '/dashboard/agents', label: 'AI Agents', icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z', section: 'main' },
  { path: '/dashboard/calls', label: 'Call Logs', icon: 'M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z', section: 'main' },
  { path: '/dashboard/phone-numbers', label: 'Phone Numbers', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 10-6 0 3 3 0 006 0z', section: 'main' },
  { path: '/dashboard/knowledge-bases', label: 'Knowledge Base', icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253', section: 'main' },
  { path: '/dashboard/analytics', label: 'Analytics', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', section: 'main' },
  { path: '/dashboard/qa', label: 'Quality Assurance', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z', section: 'main' },
  { path: '/dashboard/playground', label: 'Playground', icon: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z', section: 'main' },
  { path: '/dashboard/flows', label: 'Flow Builder', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z', section: 'main' },
  { path: '/dashboard/alerts', label: 'Alerts', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9', section: 'main' },
  { path: '/dashboard/routing', label: 'Routing', icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4', section: 'main' },
  { path: '/dashboard/connectors', label: 'Connectors', icon: 'M13 10V3L4 14h7v7l9-11h-7z', section: 'main' },
  { path: '/dashboard/agent-assist', label: 'Agent Assist', icon: 'M18 13V6a2 2 0 00-2-2H8a2 2 0 00-2 2v7m8 0V6m0 7H6m0 0v4a2 2 0 002 2h8a2 2 0 002-2v-4m-6 0h4', section: 'main' },
  { path: '/dashboard/compliance', label: 'Compliance', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', section: 'main' },
  { path: '/dashboard/workforce', label: 'Workforce', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z', section: 'main' },
  { path: '/dashboard/quickstart', label: 'Quick Start', icon: 'M13 10V3L4 14h7v7l9-11h-7z', section: 'settings' },
  { path: '/dashboard/keys', label: 'API Keys', icon: 'M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z', section: 'settings' },
  { path: '/dashboard/usage', label: 'Usage', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', section: 'settings' },
  { path: '/dashboard/billing', label: 'Billing', icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z', section: 'settings' },
];

export default function Layout() {
  const { customer, logout } = useAuth();
  const location = useLocation();
  const { status: wsStatus } = useWS();

  const planColors: Record<string, string> = {
    free: 'bg-gray-600',
    pro: 'bg-vox-600',
    enterprise: 'bg-amber-600',
  };

  return (
    <div className="min-h-screen bg-[#0f0a1e] flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1a1230] border-r border-vox-900/50 flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-vox-900/50">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-vox-500 to-vox-700 flex items-center justify-center">
              <span className="text-white font-bold text-sm">V</span>
            </div>
            <span className="text-xl font-bold text-white">VoxBridge</span>
          </Link>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.filter(i => i.section === 'main').map((item) => {
            const isActive = item.path === '/dashboard'
              ? location.pathname === '/dashboard'
              : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-vox-600/20 text-vox-300'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                </svg>
                {item.label}
              </Link>
            );
          })}

          <div className="pt-4 mt-4 border-t border-vox-900/30">
            <p className="px-3 text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-2">Settings</p>
            {navItems.filter(i => i.section === 'settings').map((item) => {
              const isActive = location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-vox-600/20 text-vox-300'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                  </svg>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-vox-900/50">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-vox-600 flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {customer?.name?.[0]?.toUpperCase() || customer?.email?.[0]?.toUpperCase() || '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{customer?.name || customer?.email}</p>
              <span className={`inline-block px-2 py-0.5 text-xs rounded-full text-white ${planColors[customer?.plan || 'free']}`}>
                {customer?.plan?.toUpperCase()}
              </span>
            </div>
          </div>
          <div className="flex items-center justify-between px-3 py-1 mb-1">
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-400 animate-pulse' : wsStatus === 'connecting' ? 'bg-amber-400' : 'bg-gray-600'}`} />
              <span className="text-[10px] text-gray-500">{wsStatus === 'connected' ? 'Live' : wsStatus === 'connecting' ? 'Connecting' : 'Offline'}</span>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full text-left text-sm text-gray-400 hover:text-white px-3 py-2 rounded-lg hover:bg-white/5 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
