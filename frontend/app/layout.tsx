import { PropsWithChildren } from 'react';
import '@/styles/globals.css';
import 'leaflet/dist/leaflet.css';
import { ThemeProvider } from './theme-provider';
import { AuthProvider } from '@/contexts/AuthContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { TAJINEProvider } from '@/contexts/TAJINEContext';
import { Toaster } from 'sonner';
import { TelemetryProvider } from '@/components/telemetry-provider';
import { Plus_Jakarta_Sans, Inter } from 'next/font/google';

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-jakarta',
  display: 'swap',
});
const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const dynamic = 'force-dynamic';

export default function RootLayout({ children }: PropsWithChildren) {
  return (
    <html lang="fr" suppressHydrationWarning className={`${jakarta.variable} ${inter.variable}`}>
      <head>
        <title>Tawiza — Intelligence Territoriale</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="description" content="TAJINE - Agent d'analyse territoriale française" />
        <meta name="keywords" content="TAJINE, intelligence territoriale, France, départements, analyse économique" />
        <link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48 64x64 128x128 256x256" />
        <link rel="icon" type="image/svg+xml" href="/logo-tajine.svg" />
        <link rel="icon" type="image/png" href="/favicon-32.png" sizes="32x32" />
        <link rel="icon" type="image/png" href="/icon-192.png" sizes="192x192" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </head>
      <body id="root" className="loading bg-background text-foreground">
        <TelemetryProvider>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
          <div className="aurora-bg" aria-hidden="true">
            <span className="aurora-blob aurora-cyan" />
            <span className="aurora-blob aurora-blue" />
            <span className="aurora-blob aurora-violet" />
          </div>
          <div className="dot-grid" aria-hidden="true" />
          <AuthProvider>
            <NotificationProvider>
              <TAJINEProvider>
                <main id="skip" className="relative z-10">{children}</main>
                <Toaster richColors position="bottom-right" />
              </TAJINEProvider>
            </NotificationProvider>
          </AuthProvider>
        </ThemeProvider>
        </TelemetryProvider>
      </body>
    </html>
  );
}
