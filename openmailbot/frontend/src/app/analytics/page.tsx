'use client'

import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/DashboardLayout'
import { BarChart3 } from 'lucide-react'

export default function AnalyticsPage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  if (status === 'unauthenticated') {
    router.push('/auth/signin')
    return null
  }

  return (
    <DashboardLayout>
      <div className="p-8">
        <div className="flex items-center mb-6">
          <BarChart3 className="w-8 h-8 text-blue-600 mr-3" />
          <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Email Volume */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Email Volume</h2>
            <div className="h-64 flex items-center justify-center text-gray-400">
              Chart placeholder - Install recharts and add LineChart
            </div>
          </div>

          {/* Response Times */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Response Times</h2>
            <div className="h-64 flex items-center justify-center text-gray-400">
              Chart placeholder - Install recharts and add BarChart
            </div>
          </div>

          {/* Top Contacts */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Top Contacts</h2>
            <div className="space-y-3">
              <ContactRow name="John Doe" emails={42} />
              <ContactRow name="Jane Smith" emails={38} />
              <ContactRow name="Bob Wilson" emails={31} />
              <ContactRow name="Alice Brown" emails={27} />
              <ContactRow name="Charlie Davis" emails={23} />
            </div>
          </div>

          {/* Sentiment Analysis */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Sentiment Analysis</h2>
            <div className="space-y-3">
              <SentimentRow label="Positive" value={65} color="green" />
              <SentimentRow label="Neutral" value={25} color="gray" />
              <SentimentRow label="Negative" value={10} color="red" />
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

function ContactRow({ name, emails }: { name: string, emails: number }) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center">
        <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 font-semibold">
          {name.split(' ').map(n => n[0]).join('')}
        </div>
        <span className="ml-3 font-medium text-gray-900">{name}</span>
      </div>
      <span className="text-sm text-gray-600">{emails} emails</span>
    </div>
  )
}

function SentimentRow({ label, value, color }: { label: string, value: number, color: string }) {
  const colorClasses = {
    green: 'bg-green-500',
    gray: 'bg-gray-400',
    red: 'bg-red-500'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-sm text-gray-600">{value}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${colorClasses[color as keyof typeof colorClasses]}`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  )
}
