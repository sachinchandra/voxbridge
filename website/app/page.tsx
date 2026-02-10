export default function Home() {
  return (
    <main>
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-gray-950/80 backdrop-blur-md border-b border-gray-800/50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">V</div>
            <span className="text-xl font-bold">VoxBridge</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-gray-400">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#providers" className="hover:text-white transition">Providers</a>
            <a href="#quickstart" className="hover:text-white transition">Quick Start</a>
            <a href="#architecture" className="hover:text-white transition">Architecture</a>
            <a href="https://github.com/sachinchandra/voxbridge" className="hover:text-white transition">GitHub</a>
          </div>
          <a href="https://github.com/sachinchandra/voxbridge"
            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-sm font-medium transition">
            Get Started
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto text-center">
          <div className="inline-block px-4 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300 text-sm mb-8">
            pip install voxbridge
          </div>

          <h1 className="text-5xl md:text-7xl font-bold leading-tight mb-6">
            One SDK.<br />
            <span className="gradient-text">Every telephony platform.</span>
          </h1>

          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-12">
            Connect any WebSocket voice bot to Twilio, Genesys, Avaya, Cisco,
            Amazon Connect, FreeSWITCH, or Asterisk. Zero custom integration code.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="#quickstart"
              className="px-8 py-3.5 rounded-lg bg-violet-600 hover:bg-violet-500 font-medium transition text-lg">
              Quick Start
            </a>
            <a href="https://github.com/sachinchandra/voxbridge"
              className="px-8 py-3.5 rounded-lg bg-gray-800 hover:bg-gray-700 font-medium transition text-lg border border-gray-700">
              View on GitHub
            </a>
          </div>
        </div>

        {/* Hero code preview */}
        <div className="max-w-3xl mx-auto mt-16">
          <div className="code-block glow">
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-gray-800">
              <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
              <span className="text-gray-500 text-xs ml-2">bridge.py</span>
            </div>
            <pre className="text-sm leading-relaxed">
              <code>
{`from voxbridge import VoxBridge

bridge = VoxBridge({
    "provider": "twilio",
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
})

@bridge.on_call_start
async def handle_call(session):
    print(f"Call from {session.from_number}")

@bridge.on_audio
async def process_audio(session, frame):
    return frame  # forward to bot

bridge.run()`}
              </code>
            </pre>
          </div>
        </div>
      </section>

      {/* Architecture Diagram */}
      <section className="py-20 px-6 bg-gray-900/30">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">How it works</h2>
            <p className="text-gray-400 text-lg">VoxBridge sits between your telephony provider and your voice bot</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800 text-center">
              <div className="text-4xl mb-4">&#128222;</div>
              <h3 className="font-semibold text-lg mb-2">Telephony Provider</h3>
              <p className="text-gray-400 text-sm">Twilio, Genesys, Avaya, Cisco, AWS Connect, FreeSWITCH, Asterisk</p>
              <div className="mt-4 text-xs text-gray-500 font-mono">mulaw / 8kHz</div>
            </div>
            <div className="p-6 rounded-xl bg-gradient-to-b from-violet-900/30 to-indigo-900/30 border border-violet-500/30 text-center glow">
              <div className="text-4xl mb-4">&#9889;</div>
              <h3 className="font-semibold text-lg mb-2 gradient-text">VoxBridge</h3>
              <p className="text-gray-400 text-sm">Protocol translation, codec conversion, session management</p>
              <div className="mt-4 text-xs text-gray-500 font-mono">serializer + codec engine</div>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800 text-center">
              <div className="text-4xl mb-4">&#129302;</div>
              <h3 className="font-semibold text-lg mb-2">Your Voice Bot</h3>
              <p className="text-gray-400 text-sm">Any WebSocket bot: STT + LLM + TTS pipeline</p>
              <div className="mt-4 text-xs text-gray-500 font-mono">pcm16 / 16kHz</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-16">Why VoxBridge?</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon: "&#128268;", title: "8 Providers Built-in", desc: "Twilio, Genesys, Avaya, Cisco, Amazon Connect, FreeSWITCH, Asterisk, and a generic WebSocket serializer." },
              { icon: "&#127925;", title: "Automatic Codec Conversion", desc: "mu-law, A-law, PCM16, and Opus. Hub-and-spoke through PCM16 means any-to-any conversion works automatically." },
              { icon: "&#9201;", title: "Zero Boilerplate", desc: "Config-driven mode: write a YAML, run one command. No code needed. Or use decorators for full control." },
              { icon: "&#128640;", title: "Async-First", desc: "Built on asyncio. Each call gets its own bidirectional task pair. Handles hundreds of concurrent calls." },
              { icon: "&#129529;", title: "Add Providers in 1 File", desc: "Implement BaseSerializer with 3 methods and 3 properties. Register it. Done. Your provider works with every bot." },
              { icon: "&#128230;", title: "pip install & go", desc: "Pure Python core with zero native dependencies. Optional extras for Opus, SIP, and FastAPI server." },
            ].map((feature, i) => (
              <div key={i} className="p-6 rounded-xl bg-gray-900/50 border border-gray-800 hover:border-violet-500/30 transition">
                <div className="text-3xl mb-4" dangerouslySetInnerHTML={{ __html: feature.icon }}></div>
                <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                <p className="text-gray-400 text-sm">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Providers Grid */}
      <section id="providers" className="py-20 px-6 bg-gray-900/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Supported Providers</h2>
          <p className="text-gray-400 text-center mb-12">Each provider has a dedicated serializer that handles its unique protocol</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: "Twilio", codec: "mulaw", rate: "8kHz", color: "red" },
              { name: "Genesys", codec: "mulaw", rate: "8kHz", color: "orange" },
              { name: "Avaya", codec: "mulaw", rate: "8kHz", color: "blue" },
              { name: "Cisco", codec: "mulaw", rate: "8kHz", color: "cyan" },
              { name: "Amazon Connect", codec: "pcm16", rate: "8kHz", color: "yellow" },
              { name: "FreeSWITCH", codec: "mulaw", rate: "8kHz", color: "green" },
              { name: "Asterisk", codec: "mulaw", rate: "8kHz", color: "purple" },
              { name: "Generic WS", codec: "pcm16", rate: "16kHz", color: "gray" },
            ].map((provider, i) => (
              <div key={i} className="p-4 rounded-xl bg-gray-900 border border-gray-800 hover:border-violet-500/30 transition text-center">
                <div className="font-semibold mb-1">{provider.name}</div>
                <div className="text-xs text-gray-500 font-mono">{provider.codec} / {provider.rate}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Quick Start */}
      <section id="quickstart" className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-16">Get Started in 60 Seconds</h2>

          <div className="space-y-8">
            {/* Step 1 */}
            <div className="flex gap-6">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center font-bold">1</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg mb-3">Install VoxBridge</h3>
                <div className="code-block">
                  <code>pip install voxbridge</code>
                </div>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex gap-6">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center font-bold">2</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg mb-3">Generate a config</h3>
                <div className="code-block">
                  <code>voxbridge init</code>
                </div>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex gap-6">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center font-bold">3</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg mb-3">Edit bridge.yaml</h3>
                <div className="code-block">
                  <pre>{`provider:
  type: genesys        # or twilio, avaya, cisco, etc.
  listen_port: 8765

bot:
  url: ws://your-bot:9000/ws
  codec: pcm16
  sample_rate: 16000`}</pre>
                </div>
              </div>
            </div>

            {/* Step 4 */}
            <div className="flex gap-6">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-violet-600 flex items-center justify-center font-bold">4</div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg mb-3">Run the bridge</h3>
                <div className="code-block">
                  <code>voxbridge run --config bridge.yaml</code>
                </div>
                <p className="text-gray-400 text-sm mt-3">
                  That&apos;s it. Your telephony provider connects to VoxBridge, and audio flows to your bot.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="py-20 px-6 bg-gray-900/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">Under the Hood</h2>
          <p className="text-gray-400 text-center mb-12">Clean, modular architecture designed for extensibility</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800">
              <h3 className="font-semibold text-violet-400 mb-2 font-mono text-sm">core/events.py</h3>
              <p className="text-gray-400 text-sm">9 Pydantic event types: AudioFrame, CallStarted, CallEnded, DTMF, Hold, Transfer, Custom, Error</p>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800">
              <h3 className="font-semibold text-violet-400 mb-2 font-mono text-sm">audio/codecs.py</h3>
              <p className="text-gray-400 text-sm">Pure-Python G.711 mu-law/A-law. Hub-and-spoke through PCM16. Optional Opus via opuslib.</p>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800">
              <h3 className="font-semibold text-violet-400 mb-2 font-mono text-sm">serializers/</h3>
              <p className="text-gray-400 text-sm">8 built-in serializers. Each is one file implementing BaseSerializer. Pure message translators &mdash; no I/O.</p>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800">
              <h3 className="font-semibold text-violet-400 mb-2 font-mono text-sm">bridge.py</h3>
              <p className="text-gray-400 text-sm">Central orchestrator. Bidirectional async loops. Decorator API. Wires serializers + codecs + transports.</p>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800">
              <h3 className="font-semibold text-violet-400 mb-2 font-mono text-sm">transports/</h3>
              <p className="text-gray-400 text-sm">WebSocket client + server transport. Optional SIP transport via PJSIP for SBC integration.</p>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800">
              <h3 className="font-semibold text-violet-400 mb-2 font-mono text-sm">session.py</h3>
              <p className="text-gray-400 text-sm">Per-call state management. Codec pipeline. Concurrent call tracking. Auto-cleanup on disconnect.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Deploy */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Deploy Anywhere</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800 text-center">
              <div className="text-3xl mb-3">&#128051;</div>
              <h3 className="font-semibold mb-2">Docker</h3>
              <div className="code-block text-xs text-left">
                <code>docker compose up</code>
              </div>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800 text-center">
              <div className="text-3xl mb-3">&#9729;&#65039;</div>
              <h3 className="font-semibold mb-2">Fly.io</h3>
              <div className="code-block text-xs text-left">
                <code>fly deploy</code>
              </div>
            </div>
            <div className="p-6 rounded-xl bg-gray-900 border border-gray-800 text-center">
              <div className="text-3xl mb-3">&#128187;</div>
              <h3 className="font-semibold mb-2">Self-hosted</h3>
              <div className="code-block text-xs text-left">
                <code>voxbridge run -c bridge.yaml</code>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Stop writing custom<br />telephony integrations.
          </h2>
          <p className="text-xl text-gray-400 mb-10">
            Build your voice bot once. Connect it everywhere.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="https://github.com/sachinchandra/voxbridge"
              className="px-8 py-4 rounded-lg bg-violet-600 hover:bg-violet-500 font-medium transition text-lg">
              Get Started on GitHub
            </a>
            <div className="px-8 py-4 rounded-lg bg-gray-800 font-mono text-lg border border-gray-700">
              pip install voxbridge
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-gray-800/50">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-bold text-xs">V</div>
            <span>VoxBridge</span>
          </div>
          <div className="flex gap-6">
            <a href="https://github.com/sachinchandra/voxbridge" className="hover:text-white transition">GitHub</a>
            <a href="https://pypi.org/project/voxbridge/" className="hover:text-white transition">PyPI</a>
            <a href="https://github.com/sachinchandra/voxbridge/blob/main/LICENSE" className="hover:text-white transition">MIT License</a>
          </div>
        </div>
      </footer>
    </main>
  )
}
