import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { keysApi } from '../services/api';
import { ApiKey } from '../types';

const steps = [
  {
    number: 1,
    title: 'Install the SDK',
    description: 'Install VoxBridge from PyPI using pip.',
  },
  {
    number: 2,
    title: 'Create an API Key',
    description: 'Generate an API key from the dashboard to authenticate your SDK.',
  },
  {
    number: 3,
    title: 'Configure Your Bridge',
    description: 'Connect your voice bot to any telephony provider with a few lines of code.',
  },
  {
    number: 4,
    title: 'Monitor Usage',
    description: 'Track calls, minutes, and provider usage in real-time on this dashboard.',
  },
];

const providers = [
  { name: 'Twilio', value: 'twilio', color: 'text-red-400' },
  { name: 'Genesys', value: 'genesys', color: 'text-orange-400' },
  { name: 'Avaya', value: 'avaya', color: 'text-blue-400' },
  { name: 'Cisco WebEx', value: 'cisco', color: 'text-cyan-400' },
  { name: 'Amazon Connect', value: 'amazon_connect', color: 'text-amber-400' },
  { name: 'FreeSWITCH', value: 'freeswitch', color: 'text-green-400' },
  { name: 'Asterisk', value: 'asterisk', color: 'text-purple-400' },
  { name: 'Generic WebSocket', value: 'generic', color: 'text-gray-400' },
];

export default function QuickStart() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('twilio');
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    keysApi.list().then(setKeys).catch(() => {});
  }, []);

  const activeKey = keys.find(k => k.status === 'active');
  const apiKeyDisplay = activeKey ? `${activeKey.key_prefix}...your_key` : 'vxb_your_api_key_here';

  const copyCode = (id: string, code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const installCode = `pip install voxbridge-io`;

  const configCode = `from voxbridge import VoxBridge

bridge = VoxBridge({
    "provider": "${selectedProvider}",
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
    "api_key": "${apiKeyDisplay}",
})

@bridge.on_call_start
async def handle_call(session):
    print(f"Call started: {session.call_id}")
    print(f"From: {session.from_number}")

@bridge.on_audio
async def process_audio(session, frame):
    # Audio flows through automatically
    # Add custom processing here if needed
    return frame

@bridge.on_call_end
async def handle_end(session, event):
    print(f"Call ended: {session.duration_ms}ms")

bridge.run()`;

  const yamlCode = `# bridge.yaml
provider:
  type: ${selectedProvider}
  listen_host: 0.0.0.0
  listen_port: 8765
  listen_path: /media-stream

bot:
  url: ws://localhost:9000/ws
  codec: pcm16
  sample_rate: 16000

saas:
  api_key: ${apiKeyDisplay}

audio:
  input_codec: mulaw
  output_codec: mulaw
  sample_rate: 8000`;

  const yamlRunCode = `voxbridge run --config bridge.yaml`;

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Quick Start Guide</h1>
      <p className="text-gray-400 mb-8">Get your voice bot connected to any telephony platform in minutes</p>

      {/* Steps overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-10">
        {steps.map((step) => (
          <div key={step.number} className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50">
            <div className="w-8 h-8 rounded-full bg-vox-600/20 flex items-center justify-center mb-3">
              <span className="text-vox-400 font-bold text-sm">{step.number}</span>
            </div>
            <h3 className="text-white font-medium text-sm mb-1">{step.title}</h3>
            <p className="text-xs text-gray-400">{step.description}</p>
          </div>
        ))}
      </div>

      {/* Step 1: Install */}
      <Section number={1} title="Install the SDK">
        <p className="text-gray-400 text-sm mb-4">
          VoxBridge is available on PyPI. Install it with pip:
        </p>
        <CodeBlock
          id="install"
          code={installCode}
          copied={copied}
          onCopy={copyCode}
        />
        <p className="text-gray-500 text-xs mt-3">
          Requires Python 3.10+. For Opus codec support, use: <code className="text-vox-400">pip install voxbridge-io[opus]</code>
        </p>
      </Section>

      {/* Step 2: API Key */}
      <Section number={2} title="Create an API Key">
        {activeKey ? (
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <p className="text-sm text-emerald-400">
                You have an active API key: <code className="font-mono">{activeKey.key_prefix}...</code> ({activeKey.name})
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
              <p className="text-sm text-amber-400">
                You don't have an API key yet.{' '}
                <Link to="/dashboard/keys" className="underline font-medium">Create one now</Link>
              </p>
            </div>
          </div>
        )}
        <p className="text-gray-400 text-sm">
          Go to <Link to="/dashboard/keys" className="text-vox-400 hover:text-vox-300">API Keys</Link> to create and manage your keys.
          The API key authenticates your SDK with VoxBridge and enables usage tracking.
        </p>
      </Section>

      {/* Step 3: Configure */}
      <Section number={3} title="Configure Your Bridge">
        {/* Provider selector */}
        <p className="text-gray-400 text-sm mb-4">Select your telephony provider:</p>
        <div className="flex flex-wrap gap-2 mb-6">
          {providers.map((p) => (
            <button
              key={p.value}
              onClick={() => setSelectedProvider(p.value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                selectedProvider === p.value
                  ? 'bg-vox-600 text-white'
                  : 'bg-[#0f0a1e] text-gray-400 hover:text-white border border-vox-900/50 hover:border-vox-600/50'
              }`}
            >
              {p.name}
            </button>
          ))}
        </div>

        {/* Tab: Programmatic vs YAML */}
        <div className="mb-4">
          <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-vox-600/20 text-vox-300 text-xs">Option A</span>
            Programmatic (Python)
          </h4>
          <CodeBlock
            id="config"
            code={configCode}
            copied={copied}
            onCopy={copyCode}
            language="python"
          />
        </div>

        <div className="my-4 flex items-center gap-4">
          <div className="flex-1 h-px bg-vox-900/50"></div>
          <span className="text-xs text-gray-500">OR</span>
          <div className="flex-1 h-px bg-vox-900/50"></div>
        </div>

        <div>
          <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-vox-600/20 text-vox-300 text-xs">Option B</span>
            Config-driven (YAML)
          </h4>
          <CodeBlock
            id="yaml"
            code={yamlCode}
            copied={copied}
            onCopy={copyCode}
            language="yaml"
          />
          <p className="text-gray-400 text-sm mt-3">Then run:</p>
          <CodeBlock
            id="yamlrun"
            code={yamlRunCode}
            copied={copied}
            onCopy={copyCode}
          />
        </div>
      </Section>

      {/* Step 4: How it works */}
      <Section number={4} title="How It Works">
        <div className="bg-[#0f0a1e] rounded-xl p-6 border border-vox-900/30">
          <div className="flex flex-col md:flex-row items-center justify-center gap-4 text-sm">
            <div className="px-4 py-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400 text-center">
              <p className="font-medium">Telephony Provider</p>
              <p className="text-xs text-blue-400/70 mt-1">{providers.find(p => p.value === selectedProvider)?.name || 'Twilio'}</p>
            </div>
            <Arrow />
            <div className="px-4 py-3 rounded-lg bg-vox-500/10 border border-vox-500/30 text-vox-400 text-center">
              <p className="font-bold">VoxBridge SDK</p>
              <p className="text-xs text-vox-400/70 mt-1">Serialization + Codec + Bridge</p>
            </div>
            <Arrow />
            <div className="px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-center">
              <p className="font-medium">Your Voice Bot</p>
              <p className="text-xs text-emerald-400/70 mt-1">WebSocket (any framework)</p>
            </div>
          </div>

          <div className="mt-6 text-center">
            <Arrow vertical />
            <div className="inline-block px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm mt-2">
              Usage reported to VoxBridge Platform (this dashboard)
            </div>
          </div>
        </div>
      </Section>

      {/* Supported features */}
      <Section number={5} title="What's Included">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FeatureCard
            title="8 Telephony Providers"
            description="Twilio, Genesys, Avaya, Cisco, Amazon Connect, FreeSWITCH, Asterisk, and Generic WebSocket."
          />
          <FeatureCard
            title="Automatic Codec Conversion"
            description="G.711 mu-law, A-law, PCM16, and Opus. Hub-and-spoke conversion through PCM16."
          />
          <FeatureCard
            title="Bidirectional Audio Bridge"
            description="Two async loops per call: provider-to-bot and bot-to-provider with resampling."
          />
          <FeatureCard
            title="Event Handlers"
            description="Decorators for call start, call end, audio frames, DTMF, hold/resume events."
          />
          <FeatureCard
            title="Usage Tracking"
            description="Call minutes auto-reported to your dashboard. Monitor usage in real-time."
          />
          <FeatureCard
            title="Zero Lock-in"
            description="Switch providers by changing one config line. Your bot code stays the same."
          />
        </div>
      </Section>

      {/* Need help */}
      <div className="mt-10 bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 text-center">
        <h3 className="text-white font-medium mb-2">Need Help?</h3>
        <p className="text-gray-400 text-sm mb-4">
          Check out the full documentation or reach out to support.
        </p>
        <div className="flex items-center justify-center gap-3">
          <a
            href="https://github.com/sachinchandra/voxbridge"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-lg bg-[#0f0a1e] text-white text-sm border border-vox-900/50 hover:border-vox-600/50 transition-colors"
          >
            GitHub Docs
          </a>
          <a
            href="https://pypi.org/project/voxbridge-io/"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-lg bg-[#0f0a1e] text-white text-sm border border-vox-900/50 hover:border-vox-600/50 transition-colors"
          >
            PyPI Package
          </a>
        </div>
      </div>
    </div>
  );
}

// ── Helper components ──────────────────────────────────────────

function Section({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-10">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-7 h-7 rounded-full bg-vox-600 flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-xs">{number}</span>
        </div>
        <h2 className="text-lg font-bold text-white">{title}</h2>
      </div>
      <div className="ml-10">
        {children}
      </div>
    </div>
  );
}

function CodeBlock({ id, code, copied, onCopy, language }: {
  id: string; code: string; copied: string | null; onCopy: (id: string, code: string) => void; language?: string;
}) {
  return (
    <div className="relative group">
      <pre className="bg-[#0f0a1e] rounded-xl p-4 border border-vox-900/30 overflow-x-auto">
        <code className="text-sm font-mono text-gray-300 whitespace-pre">{code}</code>
      </pre>
      <button
        onClick={() => onCopy(id, code)}
        className="absolute top-3 right-3 px-2.5 py-1 rounded-md bg-vox-900/50 text-xs text-gray-400 hover:text-white opacity-0 group-hover:opacity-100 transition-all"
      >
        {copied === id ? 'Copied!' : 'Copy'}
      </button>
    </div>
  );
}

function FeatureCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="bg-[#1a1230] rounded-xl p-5 border border-vox-900/50">
      <h4 className="text-white font-medium text-sm mb-1">{title}</h4>
      <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
    </div>
  );
}

function Arrow({ vertical }: { vertical?: boolean }) {
  if (vertical) {
    return (
      <div className="flex justify-center">
        <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </div>
    );
  }
  return (
    <svg className="w-6 h-6 text-gray-600 flex-shrink-0 hidden md:block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
    </svg>
  );
}
