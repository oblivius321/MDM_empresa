import { NavLink as RouterNavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Smartphone,
  Shield,
  FileText,
  Settings,
  ChevronRight,
  LogOut,
} from 'lucide-react';

const navItems = [
  { title: 'Dashboard', url: '/', icon: LayoutDashboard },
  { title: 'Dispositivos', url: '/devices', icon: Smartphone },
  { title: 'Políticas', url: '/policies', icon: Shield },
  { title: 'Logs', url: '/logs', icon: FileText },
  { title: 'Configurações', url: '/settings', icon: Settings },
];

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside className="w-60 min-h-screen flex-shrink-0 bg-[hsl(var(--sidebar-background))] border-r border-sidebar-border flex flex-col">
      {/* Logo */}
      <div className="py-8 px-4 border-b border-sidebar-border flex flex-col items-center justify-center overflow-hidden relative">
        <img
          src="/elion-logo-removebg-preview.png"
          alt="Elion Logo"
          className="w-full h-auto object-contain drop-shadow-sm scale-[1.35] mb-2"
        />
        <div className="text-[10px] font-black text-primary tracking-[0.25em] ml-1 uppercase relative z-10">
          Enterprise Console
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-2 mb-3">
          Navegação
        </p>
        {navItems.map((item) => {
          const isActive = item.url === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(item.url);
          return (
            <RouterNavLink
              key={item.url}
              to={item.url}
              end={item.url === '/'}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150 group',
                isActive ? 'sidebar-item-active' : 'sidebar-item'
              )}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{item.title}</span>
              <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-40 transition-opacity" />
            </RouterNavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-sidebar-border">
        <div className="flex items-center gap-2.5 px-1">
          <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-sm font-semibold text-primary">
            A
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">{user?.is_admin ? 'Administrador' : 'Operador'}</p>
            <p className="text-xs text-muted-foreground truncate">{user?.email || 'usuario@elion'}</p>
          </div>
          <button
            title="Sair"
            onClick={handleLogout}
            className="p-1.5 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
