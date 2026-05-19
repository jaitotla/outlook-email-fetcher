import Link from 'next/link'
import {
  Mail, Sparkles, Shield, Zap, Search, FileText, BarChart2, Users,
  Lock, Globe, Settings, CheckCircle, ChevronRight, Bot, Database,
  Layers, Cpu, MessageSquare, TrendingUp, Star, ArrowRight, GitBranch,
  Cloud, Server, Building2, User, BrainCircuit, Inbox, Clock, Send
} from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen bg-white text-gray-900">
      {/* ── Navigation ─────────────────────────────────────────────────── */}
      <nav className="bg-white/90 backdrop-blur border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-2">
              <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
                <Mail className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">OpenMailBot</span>
              <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full">Open Source</span>
            </div>
            <div className="hidden md:flex items-center space-x-8 text-sm font-medium text-gray-600">
              <a href="#features" className="hover:text-blue-600 transition">Features</a>
              <a href="#how-it-works" className="hover:text-blue-600 transition">How It Works</a>
              <a href="#integrations" className="hover:text-blue-600 transition">Integrations</a>
              <a href="#enterprise" className="hover:text-blue-600 transition">Enterprise</a>
              <a href="#pricing" className="hover:text-blue-600 transition">Pricing</a>
            </div>
            <div className="flex items-center space-x-3">
              <Link href="/auth/signin" className="text-gray-600 hover:text-blue-600 px-4 py-2 rounded-md text-sm font-medium transition">
                Sign In
              </Link>
              <Link href="/auth/signup" className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition shadow-sm">
                Get Started Free
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-5xl font-extrabold text-gray-900 sm:text-6xl md:text-7xl">
            Your AI-Powered
            <span className="text-blue-600"> Email Assistant</span>
          </h1>
          <p className="mt-6 max-w-2xl mx-auto text-xl text-gray-600">
            Manage, search, and understand your emails with the power of artificial intelligence. 
            Works with Gmail and Outlook.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Link
              href="/auth/signup"
              className="bg-blue-600 text-white px-8 py-4 rounded-lg text-lg font-semibold hover:bg-blue-700 transition shadow-lg"
            >
              Start Free Trial
            </Link>
            <Link
              href="#features"
              className="bg-white text-blue-600 px-8 py-4 rounded-lg text-lg font-semibold hover:bg-gray-50 transition shadow-lg border-2 border-blue-600"
            >
              Learn More
            </Link>
          </div>
        </div>

        {/* Features */}
        <div id="features" className="mt-32 grid md:grid-cols-3 gap-8">
          <FeatureCard
            icon={<Sparkles className="w-12 h-12 text-blue-600" />}
            title="Smart Summaries"
            description="Get instant summaries of long email threads. Understand context at a glance."
          />
          <FeatureCard
            icon={<Zap className="w-12 h-12 text-blue-600" />}
            title="AI-Powered Replies"
            description="Generate context-aware replies with adjustable tone. Save time writing emails."
          />
          <FeatureCard
            icon={<Shield className="w-12 h-12 text-blue-600" />}
            title="Semantic Search"
            description="Find emails using natural language. Search by meaning, not just keywords."
          />
        </div>

        {/* How It Works */}
        <div className="mt-32">
          <h2 className="text-4xl font-bold text-center text-gray-900 mb-16">
            How It Works
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <StepCard
              number="1"
              title="Connect Your Email"
              description="Link your Gmail or Outlook account securely with OAuth"
            />
            <StepCard
              number="2"
              title="AI Analyzes Your Emails"
              description="Our AI processes and understands your email history"
            />
            <StepCard
              number="3"
              title="Chat & Manage"
              description="Ask questions, get summaries, and generate replies instantly"
            />
          </div>
        </div>

        {/* CTA */}
        <div className="mt-32 bg-blue-600 rounded-2xl p-12 text-center">
          <h2 className="text-4xl font-bold text-white mb-4">
            Ready to transform your email experience?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join thousands of users already using OpenMailBot
          </p>
          <Link
            href="/auth/signup"
            className="inline-block bg-white text-blue-600 px-8 py-4 rounded-lg text-lg font-semibold hover:bg-gray-100 transition shadow-lg"
          >
            Get Started Now
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12 mt-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p>&copy; 2026 OpenMailBot. Open Source Email AI Assistant.</p>
          <div className="mt-4 space-x-6">
            <a href="#" className="hover:text-white">Privacy</a>
            <a href="#" className="hover:text-white">Terms</a>
            <a href="#" className="hover:text-white">GitHub</a>
          </div>
        </div>
      </footer>
    </main>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="bg-white p-8 rounded-xl shadow-lg hover:shadow-xl transition">
      <div className="mb-4">{icon}</div>
      <h3 className="text-2xl font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}

function StepCard({ number, title, description }: { number: string, title: string, description: string }) {
  return (
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 text-white rounded-full text-2xl font-bold mb-4">
        {number}
      </div>
      <h3 className="text-xl font-bold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}
