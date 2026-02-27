import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Shield, ArrowRight, UserPlus, ArrowLeft } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

export default function Login() {
    const navigate = useNavigate();
    const { toast } = useToast();
    const [isRegistering, setIsRegistering] = useState(false);

    // Form states
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    // Register extra states
    const [adminEmail, setAdminEmail] = useState('');
    const [adminPassword, setAdminPassword] = useState('');

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 segundos de limite

        try {
            const response = await fetch(`http://${window.location.hostname}:8000/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                toast({
                    title: 'Autenticação bem-sucedida',
                    description: 'Bem-vindo ao console do Elion MDM.',
                });

                localStorage.setItem('auth_token', data.access_token);

                navigate('/');
            } else {
                const errorData = await response.json();
                toast({
                    title: 'Acesso Negado',
                    description: errorData.detail || 'Email corporativo ou senha inválidos.',
                    variant: 'destructive',
                });
            }
        } catch (error: any) {
            clearTimeout(timeoutId);

            if (error.name === 'AbortError') {
                toast({
                    title: 'Tempo Excedido',
                    description: 'Os servidores demoraram para responder ou as credenciais estão incorretas.',
                    variant: 'destructive',
                });
            } else {
                toast({
                    title: 'Erro de Conexão',
                    description: 'Não foi possível se conectar com os servidores da Elion.',
                    variant: 'destructive',
                });
            }
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!email || !password || !adminEmail || !adminPassword) {
            toast({
                title: 'Falha no Cadastro',
                description: 'Preencha todos os campos do Funcionário e a Autorização do Líder.',
                variant: 'destructive',
            });
            return;
        }

        setLoading(true);

        try {
            const response = await fetch(`http://${window.location.hostname}:8000/api/auth/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    admin_email: adminEmail,
                    admin_password: adminPassword
                }),
            });

            if (response.ok) {
                toast({
                    title: 'Operador Cadastrado!',
                    description: 'Usuário liberado com sucesso. Faça login agora.',
                });
                setIsRegistering(false);
                setPassword('');
                setAdminEmail('');
                setAdminPassword('');
            } else {
                const errorData = await response.json();
                toast({
                    title: 'Assinatura Inválida',
                    description: errorData.detail || 'As credenciais do líder não autorizaram a criação do cargo.',
                    variant: 'destructive',
                });
            }
        } catch (error) {
            toast({
                title: 'Erro de Conexão',
                description: 'Não foi possível autorizar, os servidores estão inacessíveis.',
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4 relative overflow-hidden">
            {/* Background aesthetics */}
            <div className="absolute top-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
                <div className="absolute -top-[20%] -right-[10%] w-[50%] h-[50%] rounded-full bg-primary/5 blur-[120px]" />
                <div className="absolute -bottom-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-primary/5 blur-[120px]" />
            </div>

            <div className="w-full max-w-[420px] animate-fade-in relative z-10">
                <div className="flex flex-col items-center mb-8">
                    <img
                        src="/elion-logo-removebg-preview.png"
                        alt="Elion Logo"
                        className="w-48 h-auto object-contain drop-shadow-md mb-2 scale-[1.2]"
                    />
                    <span className="text-[10px] font-black text-primary tracking-[0.25em] uppercase">
                        Enterprise Console
                    </span>
                </div>

                <Card className="card-glass border border-border/50 shadow-2xl backdrop-blur-md">
                    <CardHeader className="space-y-1 pb-4">
                        <CardTitle className="text-2xl font-bold tracking-tight">
                            {isRegistering ? 'Cadastrar Novo Operador' : 'Acesso ao Sistema'}
                        </CardTitle>
                        <CardDescription className="text-sm">
                            {isRegistering
                                ? 'Autorização de administrador necessária para criar credenciais.'
                                : 'Insira suas credenciais corporativas para continuar'}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {!isRegistering ? (
                            <form onSubmit={handleLogin} className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email Corporativo</Label>
                                    <Input
                                        id="email"
                                        type="email"
                                        placeholder="admin@empresa.com"
                                        className="bg-background/50"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                    />
                                </div>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label htmlFor="password">Senha</Label>
                                        <a href="#" className="text-xs text-primary hover:underline" onClick={(e) => e.preventDefault()}>
                                            Esqueceu a senha?
                                        </a>
                                    </div>
                                    <Input
                                        id="password"
                                        type="password"
                                        placeholder="••••••••"
                                        className="bg-background/50"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                    />
                                </div>

                                <Button type="submit" className="w-full font-medium mt-6" disabled={loading}>
                                    {loading ? 'Autenticando...' : 'Entrar na Plataforma'}
                                    {!loading && <ArrowRight className="w-4 h-4 ml-2" />}
                                </Button>
                            </form>
                        ) : (
                            <form onSubmit={handleRegister} className="space-y-5">
                                {/* New User Section */}
                                <div className="space-y-3 p-4 bg-muted/20 border border-border/50 rounded-lg">
                                    <div className="flex items-center gap-2 mb-1 text-sm font-semibold text-foreground">
                                        <UserPlus className="w-4 h-4 text-primary" />
                                        <span>Dados do Novo Operador</span>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="new-email">Email do Operador</Label>
                                        <Input
                                            id="new-email"
                                            type="email"
                                            placeholder="operador@empresa.com.br"
                                            className="bg-background/50"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            required
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="new-password">Senha de Acesso</Label>
                                        <Input
                                            id="new-password"
                                            type="password"
                                            placeholder="••••••••"
                                            className="bg-background/50"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            required
                                        />
                                    </div>
                                </div>

                                {/* Admin Auth Section */}
                                <div className="space-y-3 p-4 bg-primary/5 border border-primary/20 rounded-lg">
                                    <div className="flex items-center gap-2 mb-1 text-sm font-semibold text-primary">
                                        <Shield className="w-4 h-4" />
                                        <span>Autorização de Administrador</span>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="admin-email">Líder (Email)</Label>
                                        <Input
                                            id="admin-email"
                                            type="email"
                                            placeholder="admin@empresa.com"
                                            className="bg-background/50 border-primary/20"
                                            value={adminEmail}
                                            onChange={(e) => setAdminEmail(e.target.value)}
                                            required
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="admin-password">Líder (Senha)</Label>
                                        <Input
                                            id="admin-password"
                                            type="password"
                                            placeholder="••••••••"
                                            className="bg-background/50 border-primary/20"
                                            value={adminPassword}
                                            onChange={(e) => setAdminPassword(e.target.value)}
                                            required
                                        />
                                    </div>
                                </div>

                                <Button type="submit" className="w-full font-medium text-white shadow-primary" disabled={loading}>
                                    {loading ? 'Processando autorização...' : 'Cadastrar Operador'}
                                </Button>
                            </form>
                        )}
                    </CardContent>
                    <CardFooter className="flex justify-center border-t border-border/50 pt-4 pb-6">
                        {!isRegistering ? (
                            <p className="text-xs text-muted-foreground">
                                Deseja adicionar um novo administrador?{' '}
                                <button
                                    type="button"
                                    onClick={() => setIsRegistering(true)}
                                    className="font-medium text-primary hover:underline transition-all"
                                >
                                    Registrar usuário
                                </button>
                            </p>
                        ) : (
                            <button
                                type="button"
                                onClick={() => setIsRegistering(false)}
                                className="flex items-center text-xs font-medium text-muted-foreground hover:text-foreground transition-all"
                            >
                                <ArrowLeft className="w-3 h-3 mr-1" />
                                Voltar para o login
                            </button>
                        )}
                    </CardFooter>
                </Card>

                <div className="text-center mt-8 text-xs text-muted-foreground/60">
                    <p>© 2026 Elion MDM Enterprise. Todos os direitos reservados.</p>
                    <p className="mt-1">Acesso exclusivo para funcionários autorizados.</p>
                </div>
            </div>
        </div>
    );
}
