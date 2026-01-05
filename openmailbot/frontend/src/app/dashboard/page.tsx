'use client'

import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import DashboardLayout from '@/components/DashboardLayout'
import { Mail, Clock, Users, TrendingUp } from 'lucide-react'

export default function Dashboard() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [stats, setStats] = useState({
    totalEmails: 0,
    unreadEmails: 0,
    avgResponseTime: '0h',
    topContacts: 0
  })

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/auth/signin')
    }
  }, [status, router])

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!session) {
    return null
  }

  return (
    <DashboardLayout>
      <div className="p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Welcome back, {session.user?.name?.split(' ')[0]}!
        </h1>
        <p className="text-gray-600 mb-8">Here's what's happening with your emails</p>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            icon={<Mail className="w-6 h-6 text-blue-600" />}
            title="Total Emails"
            value={stats.totalEmails.toString()}
            trend="+12% from last week"
          />
          <StatCard
            icon={<Clock className="w-6 h-6 text-orange-600" />}
            title="Unread"
            value={stats.unreadEmails.toString()}
            trend="5 need attention"
          />
          <StatCard
            icon={<TrendingUp className="w-6 h-6 text-green-600" />}
            title="Avg Response Time"
            value={stats.avgResponseTime}
            trend="2h faster"
          />
          <StatCard
            icon={<Users className="w-6 h-6 text-purple-600" />}
            title="Top Contacts"
            value={stats.topContacts.toString()}
            trend="Active this week"
          />
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl shadow p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button 
              onClick={() => router.push('/chat')}
              className="p-4 border-2 border-gray-200 rounded-lg hover:border-blue-600 hover:bg-blue-50 transition text-left"
            >
              <h3 className="font-semibold text-gray-900 mb-1">Chat with Emails</h3>
              <p className="text-sm text-gray-600">Ask questions about your emails</p>
            </button>
            <button 
              onClick={() => router.push('/analytics')}
              className="p-4 border-2 border-gray-200 rounded-lg hover:border-blue-600 hover:bg-blue-50 transition text-left"
            >
              <h3 className="font-semibold text-gray-900 mb-1">View Analytics</h3>
              <p className="text-sm text-gray-600">See insights and trends</p>
            </button>
            <button 
              onClick={() => router.push('/settings')}
              className="p-4 border-2 border-gray-200 rounded-lg hover:border-blue-600 hover:bg-blue-50 transition text-left"
            >
              <h3 className="font-semibold text-gray-900 mb-1">Settings</h3>
              <p className="text-sm text-gray-600">Configure your preferences</p>
            </button>
          </div>
        </div>

        {/* Getting Started */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl shadow-lg p-6 text-white">
          <h2 className="text-2xl font-bold mb-2">Getting Started</h2>
          <p className="mb-4 opacity-90">Complete these steps to get the most out of OpenMailBot</p>
          <div className="space-y-2">
            <div className="flex items-center">
              <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center text-blue-600 font-bold text-sm mr-3">✓</div>
              <span>Connect your email account</span>
            </div>
            <div className="flex items-center opacity-60">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center text-sm mr-3">2</div>
              <span>Configure AI settings</span>
            </div>
            <div className="flex items-center opacity-60">
              <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center text-sm mr-3">3</div>
              <span>Try your first AI query</span>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

function StatCard({ icon, title, value, trend }: { icon: React.ReactNode, title: string, value: string, trend: string }) {
  return (
    <div className="bg-white rounded-xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="p-2 bg-gray-50 rounded-lg">
          {icon}
        </div>
      </div>
      <h3 className="text-sm font-medium text-gray-600 mb-1">{title}</h3>
      <p className="text-2xl font-bold text-gray-900 mb-1">{value}</p>
      <p className="text-xs text-gray-500">{trend}</p>
    </div>
  )
}
