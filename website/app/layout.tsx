import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'VoxBridge - Universal Telephony Adapter for Voice Bots',
  description: 'Connect any WebSocket voice bot to any telephony platform. One SDK for Twilio, Genesys, Avaya, Cisco, Amazon Connect, FreeSWITCH, and Asterisk.',
  keywords: ['voice bot', 'telephony', 'twilio', 'genesys', 'avaya', 'sip', 'websocket', 'voip', 'python sdk'],
  openGraph: {
    title: 'VoxBridge - Universal Telephony Adapter',
    description: 'Connect any WebSocket voice bot to any telephony platform with zero custom integration code.',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        {children}
      </body>
    </html>
  )
}
