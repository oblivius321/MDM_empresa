import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Shield, ArrowRight, UserPlus, ArrowLeft, Eye, EyeOff } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import ForgotPassword from '@/components/ForgotPassword';
import { api } from '@/services/api';

interface SecurityQuestionOption {
    id: string;
    label: string;
}

export default function Login() {
    const navigate = useNavigate();
    const { toast } = useToast();
    const { login, register, isAuthenticated } = useAuth();
    const [isRegistering, setIsRegistering] = useState(false);
    const [isForgotPassword, setIsForgotPassword] = useState(false);
    const [loading, setLoading] = useState(false);

    // Form states - Login
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);

    // Form states - Register
    const [securityQuestion, setSecurityQuestion] = useState('');
    const [securityAnswer, setSecurityAnswer] = useState('');
    const [adminEmail, setAdminEmail] = useState('');
    const [adminPassword, setAdminPassword] = useState('');
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [showAdminPassword, setShowAdminPassword] = useState(false);
    const [securityQuestions, setSecurityQuestions] = useState<SecurityQuestionOption[]>([]);

    // Redirecionar se já autenticado
    useEffect(() => {
        if (isAuthenticated) {
            navigate('/');
        }
        
        // Fetch security questions
        const fetchQuestions = async () => {
            try {
                console.log("🔍 [SecurityQuestions] Buscando perguntas...");
                const response = await api.get('/auth/security-questions');
                console.log("✅ [SecurityQuestions] Carregadas:", response.data);
                setSecurityQuestions(response.data);
                
                if (response.data.length > 0 && !securityQuestion) {
                    setSecurityQuestion(response.data[0].id);
                }
            } catch (error) {
                console.error('❌ [SecurityQuestions] Erro:', error);
            }
        };
        fetchQuestions();
    }, [isAuthenticated, navigate]);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!email || !password) {
            toast({
                title: 'Campos Obrigatórios',
                description: 'Preencha email e senha',
                variant: 'destructive',
            });
            return;
        }

        // Evitar múltiplas submissões
        if (loading) {
            return;
        }

        setLoading(true);

        try {
            const success = await login(email, password);
            
            if (success) {
                toast({
                    title: 'Autenticação bem-sucedida',
                    description: 'Bem-vindo ao console do Elion MDM.',
                });
                // Limpar campos
                setEmail('');
                setPassword('');
                navigate('/');
            } else {
                toast({
                    title: 'Acesso Negado',
                    description: 'Email corporativo ou senha inválidos.',
                    variant: 'destructive',
                });
            }
        } catch (error: any) {
            toast({
                title: 'Erro de Conexão',
                description: error.message || 'Não foi possível se conectar com os servidores.',
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!email || !password || !adminEmail || !adminPassword || !securityQuestion || !securityAnswer) {
            toast({
                title: 'Falha no Cadastro',
                description: 'Preencha todos os campos.',
                variant: 'destructive',
            });
            return;
        }

        setLoading(true);

        try {
            const success = await register(email, password, securityQuestion, securityAnswer, adminEmail, adminPassword);
            
            if (success) {
                toast({
                    title: 'Operador Cadastrado!',
                    description: 'Usuário liberado com sucesso. Faça login agora.',
                });
                setIsRegistering(false);
                setEmail('');
                setPassword('');
                setSecurityQuestion('');
                setSecurityAnswer('');
                setAdminEmail('');
                setAdminPassword('');
            } else {
                toast({
                    title: 'Assinatura Inválida',
                    description: 'As credenciais do líder não autorizaram a criação.',
                    variant: 'destructive',
                });
            }
        } catch (error: any) {
            toast({
                title: 'Erro de Conexão',
                description: error.message || 'Não foi possível autorizar.',
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

                {/* Se está na tela de recuperação de senha, mostra o componente */}
                {isForgotPassword ? (
                    <ForgotPassword onBack={() => setIsForgotPassword(false)} />
                ) : (
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
                                            <button
                                                type="button"
                                                onClick={() => setIsForgotPassword(true)}
                                                className="text-xs text-primary hover:underline"
                                            >
                                                Esqueceu a senha?
                                            </button>
                                        </div>
                                        <div className="relative">
                                            <Input
                                                id="password"
                                                type={showPassword ? "text" : "password"}
                                                placeholder="••••••••"
                                                className="bg-background/50 pr-10"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                required
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus:outline-none"
                                            >
                                                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </button>
                                        </div>
                                    </div>

                                    <Button type="submit" className="w-full font-medium mt-6" disabled={loading}>
                                        {loading ? 'Autenticando...' : 'Entrar na Plataforma'}
                                        {!loading && <ArrowRight className="w-4 h-4 ml-2" />}
                                    </Button>
                                </form>
                            ) : (
                                <form onSubmit={handleRegister} className="space-y-5">
                                    {/* New User Section */}
                                    <div className="space-y-3 p-4 bg-muted/20 border border-border/50 rounded-lg max-h-96 overflow-y-auto">
                                        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-foreground sticky top-0 bg-muted/20">
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
                                            <div className="relative">
                                                <Input
                                                    id="new-password"
                                                    type={showNewPassword ? "text" : "password"}
                                                    placeholder="••••••••"
                                                    className="bg-background/50 pr-10"
                                                    value={password}
                                                    onChange={(e) => setPassword(e.target.value)}
                                                    required
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => setShowNewPassword(!showNewPassword)}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus:outline-none"
                                                >
                                                    {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                                </button>
                                            </div>
                                        </div>
                                        
                                        {/* Security Question Section */}
                                        <div className="pt-3 border-t border-border/30">
                                            <p className="text-xs font-semibold text-muted-foreground mb-3">Pergunta de Segurança (para recuperação de senha)</p>
                                            <div className="space-y-2">
                                                <Label htmlFor="security-question">Escolha uma Pergunta</Label>
                                                <select
                                                    id="security-question"
                                                    className="w-full h-10 px-3 py-2 rounded-md border border-input bg-background/50 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                                                    value={securityQuestion}
                                                    onChange={(e) => setSecurityQuestion(e.target.value)}
                                                    required
                                                >
                                                    <option value="" disabled>Selecione uma pergunta...</option>
                                                    {securityQuestions.map((q) => (
                                                        <option key={q.id} value={q.id}>
                                                            {q.label}
                                                        </option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="space-y-2 mt-2">
                                                <Label htmlFor="security-answer">Resposta</Label>
                                                <Input
                                                    id="security-answer"
                                                    type="text"
                                                    placeholder="Ex: Roxo"
                                                    className="bg-background/50 text-sm"
                                                    value={securityAnswer}
                                                    onChange={(e) => setSecurityAnswer(e.target.value)}
                                                    required
                                                />
                                            </div>
                                            <p className="text-xs text-muted-foreground mt-2">💡 Use uma pergunta e resposta que só você saiba</p>
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
                                            <div className="relative">
                                                <Input
                                                    id="admin-password"
                                                    type={showAdminPassword ? "text" : "password"}
                                                    placeholder="••••••••"
                                                    className="bg-background/50 border-primary/20 pr-10"
                                                    value={adminPassword}
                                                    onChange={(e) => setAdminPassword(e.target.value)}
                                                    required
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => setShowAdminPassword(!showAdminPassword)}
                                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus:outline-none"
                                                >
                                                    {showAdminPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                                </button>
                                            </div>
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
                )}

                <div className="text-center mt-8 text-xs text-muted-foreground/60">
                    <p>© 2026 Elion MDM Enterprise. Todos os direitos reservados.</p>
                    <p className="mt-1">Acesso exclusivo para funcionários autorizados.</p>
                </div>
            </div>
        </div>
    );
}
