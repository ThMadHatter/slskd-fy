import type { Metadata } from 'next';
import './globals.css';
import Providers from '../components/Providers';
import ClientLayout from '../components/ClientLayout';

export const metadata: Metadata = {
  title: 'Sonic Archive - Technical Audiophile V1',
  description: 'Precision-machined audio cataloging and transfer client for Soulseek.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap"
        />
      </head>
      <body className="antialiased overflow-hidden bg-[#0a0a0b] text-[#e5e2e3]">
        <Providers>
          <ClientLayout>{children}</ClientLayout>
        </Providers>
      </body>
    </html>
  );
}
