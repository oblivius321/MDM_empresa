import { AppSidebar } from '@/components/AppSidebar';
import { Outlet } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

export function Layout() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="flex min-h-screen w-full bg-background">
      <AppSidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
