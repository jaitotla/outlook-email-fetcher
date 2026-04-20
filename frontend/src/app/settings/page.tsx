'use client'

import { useSession } from 'next-auth/react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/DashboardLayout'
import { Settings as SettingsIcon, Save, Slack } from 'lucide-react'
import { slackApi, type SlackWorkspace } from '@/lib/api/slack'
import ConnectionButton from '@/components/slack/ConnectionButton'
import WorkspaceCard from '@/components/slack/WorkspaceCard'
import WorkspaceConfigModal from '@/components/slack/WorkspaceConfigModal'

export default function SettingsPage() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [settings, setSettings] = useState({
    llmProvider: 'openai',
    llmModel: 'gpt-4',
    embeddingProvider: 'openai',
    vectorDb: 'pinecone',
    tone: 'professional',
    autoSync: true,
    syncFrequency: '15'
  })
  const [isSaving, setIsSaving] = useState(false)
  const [slackWorkspaces, setSlackWorkspaces] = useState<SlackWorkspace[]>([])
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(false)
  const [selectedWorkspace, setSelectedWorkspace] = useState<SlackWorkspace | null>(null)
  const [showConfigModal, setShowConfigModal] = useState(false)

  useEffloadSlackWorkspaces = async () => {
    setIsLoadingWorkspaces(true)
    try {
      const data = await slackApi.getWorkspaces()
      setSlackWorkspaces(data.workspaces || [])
    } catch (error) {
      console.error('Failed to load Slack workspaces:', error)
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }

  const handleSlackConnect = () => {
    slackApi.connect()
  }

  const handleConfigureWorkspace = (workspaceId: string) => {
    const workspace = slackWorkspaces.find(w => w.workspaceId === workspaceId)
    if (workspace) {
      setSelectedWorkspace(workspace)
      setShowConfigModal(true)
    }
  }

  const handleSyncWorkspace = async (workspaceId: string) => {
    try {
      await slackApi.syncWorkspace(workspaceId)
      alert('Sync started successfully!')
      loadSlackWorkspaces()
    } catch (error) {
      console.error('Failed to sync workspace:', error)
      alert('Failed to start sync')
    }
  }

  const handleDisconnectWorkspace = async (workspaceId: string) => {
    if (!confirm('Are you sure you want to disconnect this workspace?')) return
    
    try {
      await slackApi.disconnectWorkspace(workspaceId)
      alert('Workspace disconnected successfully!')
      loadSlackWorkspaces()
    } catch (error) {
      console.error('Failed to disconnect workspace:', error)
      alert('Failed to disconnect workspace')
    }
  }

  const ect(() => {
    loadSlackWorkspaces()
    
    // Check for OAuth success/error
    const slackConnected = searchParams?.get('slack_connected')
    const slackError = searchParams?.get('slack_error')
    
    if (slackConnected === 'true') {
      alert('Slack workspace connected successfully!')
      loadSlackWorkspaces()
      // Clear URL params
      window.history.replaceState({}, '', '/settings')
    } else if (slackError) {
      alert(`Slack connection failed: ${slackError}`)
      window.history.replaceState({}, '', '/settings')
    }
  }, [searchParams])

  if (status === 'unauthenticated') {
    router.push('/auth/signin')
    return null
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      // TODO: Call backend API
      await new Promise(resolve => setTimeout(resolve, 1000))
      alert('Settings saved successfully!')
    } catch (error) {
      console.error('Save error:', error)
      alert('Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <DashboardLayout>
      <div className="p-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <SettingsIcon className="w-8 h-8 text-blue-600 mr-3" />
            <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
          </div>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition"
          >
            <Save className="w-5 h-5 mr-2" />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        <div className="max-w-2xl space-y-6">
          {/* Slack Integration */}
          <div className="bg-white rounded-xl shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Slack className="w-6 h-6 text-[#4A154B]" />
                <h2 className="text-xl font-bold text-gray-900">Slack Integration</h2>
              </div>
              {slackWorkspaces.length === 0 && (
                <ConnectionButton onConnect={handleSlackConnect} />
              )}
            </div>
            
            {isLoadingWorkspaces ? (
              <div className="text-center py-8 text-gray-500">
                Loading workspaces...
              </div>
            ) : slackWorkspaces.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-600 mb-4">
                  Connect your Slack workspace to sync messages and enable AI-powered features
                </p>
                <ul className="text-sm text-gray-500 space-y-2">
                  <li>✓ Sync channel messages and DMs</li>
                  <li>✓ Process files and attachments</li>
                  <li>✓ AI-powered conversation summaries</li>
                  <li>✓ Search across all your communications</li>
                </ul>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  {slackWorkspaces.map(workspace => (
                    <WorkspaceCard
                      key={workspace.workspaceId}
                      workspace={workspace}
                      onConfigure={handleConfigureWorkspace}
                      onSync={handleSyncWorkspace}
                      onDisconnect={handleDisconnectWorkspace}
                    />
                  ))}
                </div>
                <div className="pt-4 border-t">
                  <ConnectionButton 
                    onConnect={handleSlackConnect}
                    className="w-full justify-center"
                  />
                </div>
              </>
            )}
          </div>

          {/* LLM Provider */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">AI Configuration</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  LLM Provider
                </label>
                <select
                  value={settings.llmProvider}
                  onChange={(e) => setSettings({ ...settings, llmProvider: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="ollama">Ollama (Local)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Model
                </label>
                <select
                  value={settings.llmModel}
                  onChange={(e) => setSettings({ ...settings, llmModel: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  {settings.llmProvider === 'openai' && (
                    <>
                      <option value="gpt-4">GPT-4</option>
                      <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    </>
                  )}
                  {settings.llmProvider === 'anthropic' && (
                    <>
                      <option value="claude-3-sonnet">Claude 3 Sonnet</option>
                      <option value="claude-3-haiku">Claude 3 Haiku</option>
                    </>
                  )}
                  {settings.llmProvider === 'ollama' && (
                    <>
                      <option value="llama2">Llama 2</option>
                      <option value="mistral">Mistral</option>
                    </>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Default Tone
                </label>
                <select
                  value={settings.tone}
                  onChange={(e) => setSettings({ ...settings, tone: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  <option value="professional">Professional</option>
                  <option value="semi-professional">Semi-Professional</option>
                  <option value="casual">Casual</option>
                  <option value="personal">Personal</option>
                </select>
              </div>
            </div>
          </div>

          {/* Vector Database */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Vector Database</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Vector DB Provider
                </label>
                <select
                  value={settings.vectorDb}
                  onChange={(e) => setSettings({ ...settings, vectorDb: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  <option value="pinecone">Pinecone (Cloud)</option>
                  <option value="faiss">FAISS (Local)</option>
                </select>
                <p className="mt-2 text-sm text-gray-500">
                  {settings.vectorDb === 'pinecone' 
                    ? 'Cloud-based vector search with automatic scaling'
                    : 'Local vector search for privacy and self-hosting'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Embedding Provider
                </label>
                <select
                  value={settings.embeddingProvider}
                  onChange={(e) => setSettings({ ...settings, embeddingProvider: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  <option value="openai">OpenAI (text-embedding-ada-002)</option>
                  <option value="local">Local (Sentence Transformers)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Email Sync */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Email Sync</h2>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">Auto Sync</p>
                  <p className="text-sm text-gray-600">Automatically sync new emails</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.autoSync}
                    onChange={(e) => setSettings({ ...settings, autoSync: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {settings.autoSync && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sync Frequency (minutes)
                  </label>
                  <input
                    type="number"
                    value={settings.syncFrequency}
                    onChange={(e) => setSettings({ ...settings, syncFrequency: e.target.value })}
                    min="5"
                    max="60"
                    className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
                  />
                </div>
              )}
            </div>
          </div>

          {/* Account */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Account</h2>
            
            <div className="space-y-3">
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-700">Email</span>
                <span className="font-medium text-gray-900">{session?.user?.email}</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-gray-700">Provider</span>
                <span className="font-medium text-gray-900 capitalize">Google</span>
              </div>
              <div className="pt-4 border-t">
                <button className="text-red-600 hover:text-red-700 font-medium">
                  Delete Account
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Workspace Config Modal */}
      {selectedWorkspace && (
        <WorkspaceConfigModal
          workspace={selectedWorkspace}
          isOpen={showConfigModal}
          onClose={() => {
            setShowConfigModal(false)
            setSelectedWorkspace(null)
          }}
          onSave={loadSlackWorkspaces}
        />
      )}
    </DashboardLayout>
  )
}
