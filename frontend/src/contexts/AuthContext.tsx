import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id?: number;
  email: string;
  is_admin: boolean;
  is_active?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string, securityQuestion: string, securityAnswer: string, adminEmail: string, adminPassword: string) => Promise<boolean>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restaurar sessão ao iniciar
  useEffect(() => {
    const savedUser = localStorage.getItem('auth_user');
    const savedToken = localStorage.getItem('auth_token');

    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (err) {
        console.error('Erro ao restaurar sessão:', err);
        localStorage.removeItem('auth_user');
      }
    }

    if (savedToken) {
      importApi().then((api) => {
        api.defaults.headers.common.Authorization = `Bearer ${savedToken}`;
      });
    }

    setLoading(false);
  }, []);

  const importApi = async () => {
    // Dynamic import inside actions to avoid circular dependencies if any
    const { api } = await import('../services/api');
    return api;
  };

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      console.log(`🔐 [AuthContext] Login attempt: ${email}`);
      const api = await importApi();
      
      console.log(`🔐 [AuthContext] api.baseURL = ${api.defaults.baseURL}`);
      console.log(`🔐 [AuthContext] api.defaults = `, api.defaults);
      
      const response = await api.post('/auth/login', { email, password });

      console.log(`✅ [AuthContext] Login successful!`);
      console.log(`✅ [AuthContext] Response status: ${response.status}`);
      console.log(`✅ [AuthContext] Response data:`, response.data);

      const data = response.data;
      const accessToken = data.access_token;

      if (!accessToken) {
        throw new Error('Login não retornou access_token.');
      }

      localStorage.setItem('auth_token', accessToken);
      api.defaults.headers.common.Authorization = `${data.token_type || 'bearer'} ${accessToken}`;

      const meResponse = await api.get('/auth/me');
      const me = meResponse.data;

      const userPayload = {
        id: me.id,
        email: me.email,
        is_admin: me.is_admin || false,
        is_active: me.is_active,
      };

      setUser(userPayload);

      // Salvar apenas dados não-sensíveis no localStorage
      localStorage.setItem('auth_user', JSON.stringify(userPayload));

      return true;
    } catch (error: any) {
      console.error('❌ [AuthContext] Login error:', error);
      if (error.response) {
        console.error(`❌ [AuthContext] Status: ${error.response.status}`);
        console.error(`❌ [AuthContext] Response:`, error.response.data);
      } else if (error.request) {
        console.error('❌ [AuthContext] No response received:', error.request);
      } else {
        console.error('❌ [AuthContext] Error message:', error.message);
      }
      return false;
    }
  };

  const register = async (
    email: string,
    password: string,
    securityQuestion: string,
    securityAnswer: string,
    adminEmail: string,
    adminPassword: string
  ): Promise<boolean> => {
    try {
      const api = await importApi();
      await api.post('/auth/register', {
        email,
        password,
        security_question: securityQuestion,
        security_answer: securityAnswer,
        admin_email: adminEmail,
        admin_password: adminPassword,
      });

      return true;
    } catch (error) {
      console.error('Erro no registro:', error);
      return false;
    }
  };

  const logout = async () => {
    try {
      const api = await importApi();
      await api.post('/auth/logout');
    } catch (e) { /* ignore */ }

    setUser(null);
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_token');
    try {
      const api = await importApi();
      delete api.defaults.headers.common.Authorization;
    } catch (e) { /* ignore */ }
  };

  const refreshToken = async (): Promise<boolean> => {
    try {
      const api = await importApi();
      const token = localStorage.getItem('auth_token');
      if (token) {
        api.defaults.headers.common.Authorization = `Bearer ${token}`;
      }
      const response = await api.get('/auth/me');
      const currentUser = response.data;
      const userPayload = {
        id: currentUser.id,
        email: currentUser.email,
        is_admin: currentUser.is_admin || false,
        is_active: currentUser.is_active,
      };
      setUser(userPayload);
      localStorage.setItem('auth_user', JSON.stringify(userPayload));
      return true;
    } catch {
      setUser(null);
      localStorage.removeItem('auth_user');
      localStorage.removeItem('auth_token');
      return false;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth deve ser usado dentro de AuthProvider');
  }
  return context;
}
