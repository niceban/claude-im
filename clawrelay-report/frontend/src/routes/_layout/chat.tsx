import { useSuspenseQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  Bot,
  CheckCircle,
  ChevronDown,
  Clock,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Send,
  User,
  XCircle,
} from "lucide-react"
import { Suspense, useEffect, useRef, useState } from "react"

import { MetricsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"

// ============================================================================
// Types
// ============================================================================

interface Session {
  relay_session_id: string
  owner_id: string
  created_at: string
  last_active: number
}

interface SessionsResponse {
  sessions: Session[]
  total: number
  timestamp?: string
}

interface ChatMessage {
  timestamp: string
  bot_key: string
  user_id: string
  stream_id: string
  relay_session_id: string
  cli_session_id?: string
  chat_type: string
  session_key: string
  message_type: string
  message: string
  response: string
  tools_used: any
  status: string
  error: string | null
  latency_ms: number
  request_at: string
}

interface ToolCall {
  name: string
  status: "running" | "completed"
}

// ============================================================================
// Route
// ============================================================================

export const Route = createFileRoute("/_layout/chat")({
  component: ChatPage,
  head: () => ({
    meta: [{ title: "Chat - Clawrelay Report" }],
  }),
})

// ============================================================================
// Page Component
// ============================================================================

function ChatPage() {
  return (
    <Suspense fallback={<ChatLoading />}>
      <ChatContent />
    </Suspense>
  )
}

function ChatLoading() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full max-w-2xl" />
      </div>
    </div>
  )
}

// ============================================================================
// Main Chat Content
// ============================================================================

function ChatContent() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // Session state
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])

  // Tool panel state
  const [toolPanelOpen, setToolPanelOpen] = useState(true)

  // Fetch sessions list
  const { data: sessionsData } = useSuspenseQuery({
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000"
      const resp = await fetch(`${apiUrl}/api/v1/chat/sessions`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token") || ""}` },
      })
      if (!resp.ok) return { sessions: [], total: 0 }
      return resp.json() as Promise<{ sessions: Session[]; total: number; timestamp?: string }>
    },
    queryKey: ["chat-sessions"],
    refetchInterval: 30000,
  })

  // Initialize sessions from API
  useEffect(() => {
    if (sessionsData?.sessions) {
      setSessions(sessionsData.sessions)
      // Auto-select first session if none selected
      if (!selectedSessionId && sessionsData.sessions.length > 0) {
        setSelectedSessionId(sessionsData.sessions[0].relay_session_id)
      }
    }
  }, [sessionsData])

  // Create new session
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newSessionMessage, setNewSessionMessage] = useState("")
  const [isCreating, setIsCreating] = useState(false)

  const handleCreateSession = async () => {
    if (isCreating) return
    setIsCreating(true)
    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000"
      const resp = await fetch(`${apiUrl}/api/v1/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: newSessionMessage }),
      })
      if (resp.ok) {
        const data = await resp.json()
        setCreateDialogOpen(false)
        setNewSessionMessage("")
        queryClient.invalidateQueries({ queryKey: ["sessions"] })
        if (data.relay_session_id) {
          setSelectedSessionId(data.relay_session_id)
        }
      }
    } finally {
      setIsCreating(false)
    }
  }

  // Switch session
  const handleSwitchSession = (sessionId: string) => {
    setSelectedSessionId(sessionId)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with session selector */}
      <ChatHeader
        sessions={sessions}
        selectedSessionId={selectedSessionId}
        onSwitchSession={handleSwitchSession}
        onCreateSession={() => setCreateDialogOpen(true)}
        currentUser={currentUser}
      />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Center: Conversation area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedSessionId ? (
            <ConversationView
              sessionId={selectedSessionId}
              onToolCall={(tool) => {
                // Tool calls are tracked internally
              }}
            />
          ) : (
            <EmptyState onCreateSession={() => setCreateDialogOpen(true)} />
          )}
        </div>

        {/* Right: Tool status panel */}
        {selectedSessionId && (
          <div className={`transition-all duration-200 ${toolPanelOpen ? "w-80" : "w-12"}`}>
            <ToolStatusPanel
              sessionId={selectedSessionId}
              isOpen={toolPanelOpen}
              onToggle={() => setToolPanelOpen(!toolPanelOpen)}
            />
          </div>
        )}
      </div>

      {/* Create session dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建会话</DialogTitle>
            <DialogDescription>
              创建一个新的 Claude 对话会话。你可以在下方输入第一条消息。
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              placeholder="第一条消息（可选）..."
              value={newSessionMessage}
              onChange={(e) => setNewSessionMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleCreateSession()
                }
              }}
              disabled={isCreating}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)} disabled={isCreating}>
              取消
            </Button>
            <Button onClick={handleCreateSession} disabled={isCreating}>
              {isCreating ? "创建中..." : "创建并发送"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ============================================================================
// Chat Header with Session Selector
// ============================================================================

interface ChatHeaderProps {
  sessions: Session[]
  selectedSessionId: string | null
  onSwitchSession: (id: string) => void
  onCreateSession: () => void
  currentUser: any
}

function ChatHeader({
  sessions,
  selectedSessionId,
  onSwitchSession,
  onCreateSession,
  currentUser,
}: ChatHeaderProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [renameSessionId, setRenameSessionId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleRename = async (sessionId: string) => {
    if (!renameValue.trim()) return
    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000"
      await fetch(`${apiUrl}/api/v1/chat/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: renameValue }),
      })
      setRenameSessionId(null)
      setRenameValue("")
    } catch (err) {
      console.error("Rename failed:", err)
    }
  }

  const selectedSession = sessions.find((s) => s.relay_session_id === selectedSessionId)

  return (
    <div className="flex items-center gap-4 px-6 py-4 border-b">
      {/* Session selector dropdown */}
      <div className="relative" ref={dropdownRef}>
        <Button
          variant="outline"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="min-w-[200px] justify-between"
        >
          <span className="truncate">
            {selectedSession
              ? `${selectedSession.relay_session_id.slice(0, 8)}...`
              : "选择会话"}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0" />
        </Button>

        {dropdownOpen && (
          <div className="absolute top-full left-0 mt-1 w-80 bg-background border rounded-lg shadow-lg z-50 max-h-96 overflow-auto">
            {/* Create new session */}
            <button
              onClick={() => {
                setDropdownOpen(false)
                onCreateSession()
              }}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-left text-sm"
            >
              <Plus className="h-4 w-4" />
              <span>新建会话</span>
            </button>

            <div className="border-t my-1" />

            {/* Session list */}
            {sessions.map((session) => (
              <div
                key={session.relay_session_id}
                className={`flex items-center gap-2 px-3 py-2 hover:bg-accent cursor-pointer ${
                  session.relay_session_id === selectedSessionId ? "bg-accent" : ""
                }`}
                onClick={() => {
                  onSwitchSession(session.relay_session_id)
                  setDropdownOpen(false)
                }}
              >
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs truncate">
                    {session.relay_session_id.slice(0, 12)}...
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatRelativeTime(session.last_active)}
                  </div>
                </div>

                {/* Admin rename button */}
                {currentUser?.is_superuser && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setRenameSessionId(session.relay_session_id)
                      setRenameValue(session.relay_session_id.slice(0, 8))
                    }}
                    className="p-1 hover:bg-accent rounded"
                    title="重命名"
                  >
                    ✏️
                  </button>
                )}

                {/* Rename input */}
                {renameSessionId === session.relay_session_id && (
                  <div
                    className="flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleRename(session.relay_session_id)
                        if (e.key === "Escape") setRenameSessionId(null)
                      }}
                      className="h-6 w-24 text-xs"
                      autoFocus
                    />
                  </div>
                )}
              </div>
            ))}

            {sessions.length === 0 && (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                暂无会话
              </div>
            )}
          </div>
        )}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Status */}
      {selectedSession && (
        <Badge
          className={
            selectedSession.status === "completed"
              ? "bg-green-100 text-green-800"
              : selectedSession.status === "running"
                ? "bg-blue-100 text-blue-800"
                : "bg-red-100 text-red-800"
          }
        >
          {selectedSession.status}
        </Badge>
      )}
    </div>
  )
}

// ============================================================================
// Conversation View
// ============================================================================

interface ConversationViewProps {
  sessionId: string
  onToolCall?: (tool: string) => void
}

function ConversationView({ sessionId, onToolCall }: ConversationViewProps) {
  const [inputMessage, setInputMessage] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [wsMessages, setWsMessages] = useState<Array<{ role: string; content: string }>>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Fetch initial history
  const { data: rawMessages, refetch } = useSuspenseQuery({
    queryFn: () =>
      MetricsService.readConversation({ relaySessionId: sessionId }) as Promise<ChatMessage[]>,
    queryKey: ["conversation", sessionId],
  })

  // WebSocket connection
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/api/v1/ws/${sessionId}`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === "message" || data.type === "delta") {
          setWsMessages((prev) => {
            const last = prev[prev.length - 1]
            if (data.type === "delta" && last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { role: "assistant", content: (last.content || "") + (data.content || "") },
              ]
            }
            return [...prev, { role: data.role || "assistant", content: data.content || "" }]
          })

          // Notify tool panel about tool use (if we had that info from WS)
        } else if (data.type === "done") {
          refetch()
          setIsSending(false)
          setInputMessage("")
        } else if (data.type === "error") {
          setIsSending(false)
        }
      } catch {
        // Ignore parse errors
      }
    }

    ws.onclose = () => {
      // Optionally implement reconnect
    }
    ws.onerror = () => {
      // Optionally implement reconnect
    }

    return () => {
      ws.close()
    }
  }, [sessionId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [wsMessages])

  // Send message
  const handleSend = async () => {
    if (!inputMessage.trim() || isSending) return
    setIsSending(true)
    setWsMessages((prev) => [...prev, { role: "user", content: inputMessage }])
    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000"
      await fetch(`${apiUrl}/api/v1/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: inputMessage }),
      })
    } catch {
      setIsSending(false)
    }
  }

  const messages = (rawMessages as ChatMessage[]) || []

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-auto p-6 space-y-4">
        {/* Historical messages */}
        {messages.map((msg, i) => {
          if (msg.message && !msg.response) {
            return (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                  <User className="h-4 w-4 text-blue-600" />
                </div>
                <div className="flex-1">
                  <div className="font-medium text-sm mb-1">
                    {msg.user_id?.slice(0, 16)}...
                  </div>
                  <div className="text-sm bg-blue-50 dark:bg-blue-950/50 rounded-lg p-3">
                    {msg.message}
                  </div>
                </div>
              </div>
            )
          } else if (msg.response) {
            return (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-green-600" />
                </div>
                <div className="flex-1">
                  <div className="font-medium text-sm mb-1">{msg.bot_key}</div>
                  <div className="text-sm bg-green-50 dark:bg-green-950/50 rounded-lg p-3">
                    {msg.response}
                  </div>
                  {msg.tools_used && msg.tools_used.length > 0 && (
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {msg.tools_used.map((tool: string, j: number) => (
                        <Badge key={j} variant="outline" className="text-xs">
                          {tool}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          }
          return null
        })}

        {/* WebSocket messages (real-time) */}
        {wsMessages.map((msg, i) => (
          <div key={`ws-${i}`} className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
              <Bot className="h-4 w-4 text-green-600" />
            </div>
            <div className="flex-1">
              <div className="font-medium text-sm mb-1">Assistant</div>
              <div className="text-sm bg-green-50 dark:bg-green-950/50 rounded-lg p-3">
                {msg.content}
              </div>
            </div>
          </div>
        ))}

        {/* Sending indicator */}
        {isSending && (
          <div className="flex gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
              <Bot className="h-4 w-4 text-green-600" />
            </div>
            <div className="flex-1">
              <div className="font-medium text-sm mb-1">Assistant</div>
              <div className="text-sm text-muted-foreground italic">处理中...</div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t p-4">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <Input
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="输入消息..."
            disabled={isSending}
            className="flex-1"
          />
          <Button onClick={handleSend} disabled={!inputMessage.trim() || isSending}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Tool Status Panel
// ============================================================================

interface ToolStatusPanelProps {
  sessionId: string
  isOpen: boolean
  onToggle: () => void
}

function ToolStatusPanel({ sessionId, isOpen, onToggle }: ToolStatusPanelProps) {
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([])

  // Connect to WebSocket to receive tool events
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/api/v1/ws/${sessionId}`)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        // We don't have direct tool events from WS, but we could track via message flow
      } catch {
        // Ignore
      }
    }

    ws.onclose = () => {}
    ws.onerror = () => {}

    return () => {
      ws.close()
    }
  }, [sessionId])

  // For now, show placeholder since ToolUseStart events aren't in the current WS protocol
  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="h-full w-12 flex items-center justify-center border-l hover:bg-accent transition-colors"
        title="展开工具状态"
      >
        <PanelRightOpen className="h-4 w-4" />
      </button>
    )
  }

  return (
    <div className="h-full border-l flex flex-col bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4" />
          <span className="font-medium text-sm">Tools</span>
        </div>
        <button
          onClick={onToggle}
          className="p-1 hover:bg-accent rounded"
          title="折叠工具状态"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* Tool list */}
      <div className="flex-1 overflow-auto p-3">
        {toolCalls.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-8">
            工具调用将显示在这里
          </div>
        ) : (
          <div className="space-y-2">
            {toolCalls.map((tool, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-sm p-2 rounded bg-accent/50"
              >
                <div className="flex-shrink-0">
                  {tool.status === "completed" ? (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-yellow-500 animate-pulse" />
                  )}
                </div>
                <span className="font-mono text-xs">{tool.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Empty State
// ============================================================================

function EmptyState({ onCreateSession }: { onCreateSession: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="text-muted-foreground mb-4">
        <MessageSquare className="h-16 w-16 mx-auto opacity-20" />
      </div>
      <h3 className="text-lg font-medium mb-2">暂无会话</h3>
      <p className="text-sm text-muted-foreground mb-4">
        创建一个新会话开始和 Claude 对话
      </p>
      <Button onClick={onCreateSession}>
        <Plus className="h-4 w-4 mr-2" />
        新建会话
      </Button>
    </div>
  )
}

// ============================================================================
// Helpers
// ============================================================================

function formatRelativeTime(dateStr: string | undefined): string {
  if (!dateStr) return "N/A"
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days}天前`
    if (hours > 0) return `${hours}小时前`
    if (minutes > 0) return `${minutes}分钟前`
    return "刚刚"
  } catch {
    return dateStr
  }
}
