import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowLeft, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { apiClient } from '@/services/api';

type ForgotPasswordStep = 'email' | 'security-question' | 'new-password' | 'success';

interface ForgotPasswordProps {
    onBack: () => void;
}

export default function ForgotPassword({ onBack }: ForgotPasswordProps) {
    const { toast } = useToast();
    const [step, setStep] = useState<ForgotPasswordStep>('email');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Step 1: Email
    const [email, setEmail] = useState('');

    // Step 2: Security Question
    const [securityQuestion, setSecurityQuestion] = useState('');
    const [securityAnswer, setSecurityAnswer] = useState('');
    const [resetToken, setResetToken] = useState('');

    // Step 3: New Password
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    // ============= STEP 1: EMAIL =============
    const handleEmailSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (!email.trim()) {
            setError('Digite seu email corporativo');
            return;
        }

        setLoading(true);

        try {
            const response = await apiClient.post('/auth/forgot-password', {
                email
            });

            setSecurityQuestion(response.data.security_question);
            setResetToken(response.data.reset_token);
            setStep('security-question');

            toast({
                title: 'Pergunta carregada',
                description: 'Responda a sua pergunta de segurança para continuar',
            });
        } catch (err: any) {
            const message = err.response?.data?.detail || 'Email não encontrado';
            setError(message);
            toast({
                title: 'Erro',
                description: message,
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };

    // ============= STEP 2: SECURITY QUESTION =============
    const handleSecurityAnswerSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (!securityAnswer.trim()) {
            setError('Digite a resposta para a pergunta de segurança');
            return;
        }

        setLoading(true);

        try {
            const response = await apiClient.post('/auth/verify-security-answer', {
                email,
                security_answer: securityAnswer
            });

            setResetToken(response.data.reset_token);
            setStep('new-password');

            toast({
                title: 'Resposta correta!',
                description: 'Agora escolha uma nova senha',
            });
        } catch (err: any) {
            const message = err.response?.data?.detail || 'Resposta incorreta';
            setError(message);
            toast({
                title: 'Erro',
                description: message,
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };

    // ============= STEP 3: NEW PASSWORD =============
    const handlePasswordReset = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        // Validações
        if (!newPassword.trim() || !confirmPassword.trim()) {
            setError('Preencha ambos os campos de senha');
            return;
        }

        if (newPassword.length < 6) {
            setError('Senha deve ter no mínimo 6 caracteres');
            return;
        }

        if (newPassword !== confirmPassword) {
            setError('As senhas não coincidem');
            return;
        }

        setLoading(true);

        try {
            await apiClient.post('/auth/reset-password', {
                email,
                new_password: newPassword,
                confirm_password: confirmPassword
            });

            setStep('success');

            toast({
                title: 'Sucesso!',
                description: 'Sua senha foi atualizada. Vous pouvez agora fazer login com a nova senha.',
            });

            // Redireciona para login após 2 segundos
            setTimeout(() => {
                onBack();
            }, 2000);
        } catch (err: any) {
            const message = err.response?.data?.detail || 'Erro ao resetar senha';
            setError(message);
            toast({
                title: 'Erro',
                description: message,
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };

    // ============= RENDER =============

    return (
        <div className="w-full max-w-md mx-auto">
            {/* STEP 1: EMAIL INPUT */}
            {step === 'email' && (
                <Card className="border-0 shadow-lg">
                    <CardHeader className="space-y-2">
                        <CardTitle className="text-2xl">Recuperar Senha</CardTitle>
                        <CardDescription>
                            Digite seu email corporativo para começar
                        </CardDescription>
                    </CardHeader>
                    <form onSubmit={handleEmailSubmit}>
                        <CardContent className="space-y-4">
                            {error && (
                                <Alert variant="destructive">
                                    <AlertCircle className="h-4 w-4" />
                                    <AlertDescription>{error}</AlertDescription>
                                </Alert>
                            )}

                            <div className="space-y-2">
                                <Label htmlFor="email">Email Corporativo</Label>
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="seu.email@empresa.com"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    disabled={loading}
                                    autoFocus
                                />
                            </div>
                        </CardContent>
                        <CardFooter className="flex gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={onBack}
                                disabled={loading}
                                className="w-full"
                            >
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Voltar
                            </Button>
                            <Button
                                type="submit"
                                disabled={loading}
                                className="w-full"
                            >
                                {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                Continuar
                            </Button>
                        </CardFooter>
                    </form>
                </Card>
            )}

            {/* STEP 2: SECURITY QUESTION */}
            {step === 'security-question' && (
                <Card className="border-0 shadow-lg">
                    <CardHeader className="space-y-2">
                        <CardTitle className="text-xl">Pergunta de Segurança</CardTitle>
                        <CardDescription>
                            Responda sua pergunta de segurança para continuar
                        </CardDescription>
                    </CardHeader>
                    <form onSubmit={handleSecurityAnswerSubmit}>
                        <CardContent className="space-y-4">
                            {error && (
                                <Alert variant="destructive">
                                    <AlertCircle className="h-4 w-4" />
                                    <AlertDescription>{error}</AlertDescription>
                                </Alert>
                            )}

                            <div className="space-y-3 p-3 bg-slate-100 rounded-lg">
                                <p className="text-sm font-medium text-slate-600">Sua pergunta:</p>
                                <p className="text-base font-semibold text-slate-900">
                                    {securityQuestion}
                                </p>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="answer">Sua Resposta</Label>
                                <Input
                                    id="answer"
                                    type="text"
                                    placeholder="Digite sua resposta"
                                    value={securityAnswer}
                                    onChange={(e) => setSecurityAnswer(e.target.value)}
                                    disabled={loading}
                                    autoFocus
                                />
                            </div>
                        </CardContent>
                        <CardFooter className="flex gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => {
                                    setStep('email');
                                    setError('');
                                }}
                                disabled={loading}
                                className="w-full"
                            >
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Voltar
                            </Button>
                            <Button
                                type="submit"
                                disabled={loading}
                                className="w-full"
                            >
                                {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                Verificar
                            </Button>
                        </CardFooter>
                    </form>
                </Card>
            )}

            {/* STEP 3: NEW PASSWORD */}
            {step === 'new-password' && (
                <Card className="border-0 shadow-lg">
                    <CardHeader className="space-y-2">
                        <CardTitle className="text-xl">Nova Senha</CardTitle>
                        <CardDescription>
                            Digite uma nova senha segura
                        </CardDescription>
                    </CardHeader>
                    <form onSubmit={handlePasswordReset}>
                        <CardContent className="space-y-4">
                            {error && (
                                <Alert variant="destructive">
                                    <AlertCircle className="h-4 w-4" />
                                    <AlertDescription>{error}</AlertDescription>
                                </Alert>
                            )}

                            <div className="space-y-2">
                                <Label htmlFor="new-password">Nova Senha</Label>
                                <Input
                                    id="new-password"
                                    type="password"
                                    placeholder="Mínimo 6 caracteres"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    disabled={loading}
                                    autoFocus
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="confirm-password">Repetir Senha</Label>
                                <Input
                                    id="confirm-password"
                                    type="password"
                                    placeholder="Repita a nova senha"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    disabled={loading}
                                />
                            </div>
                        </CardContent>
                        <CardFooter className="flex gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => {
                                    setStep('security-question');
                                    setError('');
                                }}
                                disabled={loading}
                                className="w-full"
                            >
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Voltar
                            </Button>
                            <Button
                                type="submit"
                                disabled={loading}
                                className="w-full"
                            >
                                {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                Atualizar Senha
                            </Button>
                        </CardFooter>
                    </form>
                </Card>
            )}

            {/* STEP 4: SUCCESS */}
            {step === 'success' && (
                <Card className="border-0 shadow-lg">
                    <CardContent className="pt-6">
                        <div className="text-center space-y-4">
                            <div className="flex justify-center">
                                <CheckCircle className="w-16 h-16 text-green-500" />
                            </div>
                            <h3 className="text-xl font-semibold">Senha Atualizada!</h3>
                            <p className="text-sm text-slate-600">
                                Sua senha foi alterada com sucesso. Você será redirecionado para o login em momentos.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
