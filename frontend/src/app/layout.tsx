import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Indian Legal Guide — AI-Powered Legal Research & Guidance',
  description:
    'Get actionable legal guidance and cited research for Indian law. Powered by AI with real statutes, case law, and expert analysis.',
  keywords: ['Indian law', 'legal research', 'legal guidance', 'AI legal', 'statutes', 'case law'],
  openGraph: {
    title: 'Indian Legal Guide',
    description: 'AI-powered legal research and actionable guidance for Indian law.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Lora:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}