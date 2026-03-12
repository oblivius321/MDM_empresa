import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  email: string;
  is_admin: boolean;
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

    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (err) {
        console.error('Erro ao restaurar sessão:', err);
        localStorage.removeItem('auth_user');
      }
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
      const api = await importApi();
      const response = await api.post('/auth/login', { email, password });

      const data = response.data;

      const userPayload = {
        email: data.user.email,
        is_admin: data.user.is_admin || false,
      };

      setUser(userPayload);

      // Salvar apenas dados não-sensíveis no localStorage
      localStorage.setItem('auth_user', JSON.stringify(userPayload));

      return true;
    } catch (error) {
      console.error('Erro no login:', error);
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
  };

  const refreshToken = async (): Promise<boolean> => {
    return !!user;
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
