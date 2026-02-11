import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Customer, AuthResponse } from '../types';
import { authApi } from '../services/api';

interface AuthContextType {
  customer: Customer | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check for existing session
    const savedToken = localStorage.getItem('voxbridge_token');
    const savedCustomer = localStorage.getItem('voxbridge_customer');

    if (savedToken && savedCustomer) {
      setToken(savedToken);
      try {
        setCustomer(JSON.parse(savedCustomer));
      } catch {
        localStorage.removeItem('voxbridge_customer');
      }
    }
    setIsLoading(false);
  }, []);

  const handleAuth = (data: AuthResponse) => {
    setToken(data.access_token);
    setCustomer(data.customer);
    localStorage.setItem('voxbridge_token', data.access_token);
    localStorage.setItem('voxbridge_customer', JSON.stringify(data.customer));
  };

  const login = async (email: string, password: string) => {
    const data = await authApi.login(email, password);
    handleAuth(data);
  };

  const signup = async (email: string, password: string, name: string) => {
    const data = await authApi.signup(email, password, name);
    handleAuth(data);
  };

  const logout = () => {
    setToken(null);
    setCustomer(null);
    localStorage.removeItem('voxbridge_token');
    localStorage.removeItem('voxbridge_customer');
  };

  return (
    <AuthContext.Provider value={{ customer, token, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
