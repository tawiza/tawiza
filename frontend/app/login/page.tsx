'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { HiEye, HiEyeSlash, HiExclamationCircle } from 'react-icons/hi2';
import { Shield } from 'lucide-react';
import { TajineLogo } from '@/components/ui/tajine-logo';

export default function LoginPage() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de connexion');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-pulse">
          <TajineLogo size={96} className="h-24 w-24" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-card border border-border rounded-xl shadow-sm">
        <CardHeader className="text-center pb-2 pt-8">
          <div className="flex justify-center mb-4">
            <div className="relative">
              <div className="absolute -inset-4 rounded-full bg-primary/8 blur-2xl animate-pulse" />
              <TajineLogo size={120} className="relative h-28 w-28 drop-shadow-lg" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
            Tawiza
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Intelligence Territoriale
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm">
                <HiExclamationCircle className="h-5 w-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="votre@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="h-11 bg-background border-border focus:border-primary"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">
                Mot de passe
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="h-11 pr-10 bg-background border-border focus:border-primary"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? (
                    <HiEyeSlash className="h-5 w-5" />
                  ) : (
                    <HiEye className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={isSubmitting || !email || !password}
              className="w-full h-11 text-base font-medium transition-colors duration-150"
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  Connexion...
                </span>
              ) : (
                'Se connecter'
              )}
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t border-border/50">
            <div className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
              <Shield className="h-3 w-3" />
              <span>Connexion securisee — Tawiza v2.17</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
