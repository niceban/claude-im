import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Bot, CheckCircle, Clock, MessageSquare, Send, User, XCircle } from "lucide-react"
import { Suspense, useEffect, useRef, useState } from "react"

import { MetricsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "N/A"
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

function formatLatency(ms: number | undefined): string {
  if (!ms) return "N/A"
  if (ms >= 60000) return (ms / 60000).toFixed(1) + " min"
  if (ms >= 1000) return (ms / 1000).toFixed(1) + " s"
  return ms + " ms"
}

export const Route = createFileRoute("/_layout/sessions/$sessionId")({
  component: SessionDetailPage,
  head: () => ({
    meta: [{ title: "Session Detail - Clawrelay Report" }],
  }),
})

// Message type from chat.jsonl
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

function SessionDetailContent() {
  const { sessionId } = Route.useParams()
  const [inputMessage, setInputMessage] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [wsMessages, setWsMessages] = useState<Array<{role: string; content: string}>>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Fetch initial history (from chat.jsonl)
  const { data: rawMessages, refetch } = useSuspenseQuery({
    queryFn: () => MetricsService.readConversation({ relaySessionId: sessionId }) as Promise<ChatMessage[]>,
    queryKey: ["conversation", sessionId],
  })

  // Connect to WebSocket for real-time updates (admin sessions)
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
              return [...prev.slice(0, -1), { role: "assistant", content: (last.content || "") + (data.content || "") }]
            }
            return [...prev, { role: data.role || "assistant", content: data.content || "" }]
          })
        } else if (data.type === "done") {
          refetch()
          setIsSending(false)
          setInputMessage("")
        } else if (data.type === "error") {
          setIsSending(false)
        }
      } catch {}
    }

    ws.onclose = () => {}
    ws.onerror = () => {}

    return () => {
      ws.close()
    }
  }, [sessionId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [wsMessages])

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
      // Response comes via WebSocket; refetch on done
    } catch (err) {
      setIsSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const messages = rawMessages as ChatMessage[]

  // Aggregate stats from messages
  const totalMessages = messages.length
  const successCount = messages.filter((m) => m.status === "success").length
  const errorCount = messages.filter((m) => m.status === "error").length
  const totalLatency = messages.reduce((sum: number, m) => sum + (m.latency_ms || 0), 0)
  const avgLatency = totalLatency / totalMessages

  // Get unique users and bots
  const users = [...new Set(messages.map((m) => m.user_id).filter(Boolean))]
  const bots = [...new Set(messages.map((m) => m.bot_key).filter(Boolean))]

  // Group by stream_id (each user message + AI response pair)
  const conversationPairs: Array<{ user: ChatMessage; assistant: ChatMessage | null }> = []
  let currentPair: { user: ChatMessage; assistant: ChatMessage | null } | null = null

  for (const msg of messages) {
    if (msg.message && !msg.response) {
      // User message
      currentPair = { user: msg, assistant: null }
    } else if (currentPair && msg.response && !msg.message) {
      // Assistant response
      currentPair.assistant = msg
      conversationPairs.push(currentPair)
      currentPair = null
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Session Detail</h1>
        <p className="text-muted-foreground font-mono text-sm">{sessionId}</p>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Messages</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalMessages}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Users</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{users.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Bots</CardTitle>
            <Bot className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{bots.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Latency</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatLatency(avgLatency)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Status</CardTitle>
            {errorCount > 0 ? (
              <XCircle className="h-4 w-4 text-red-500" />
            ) : (
              <CheckCircle className="h-4 w-4 text-green-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Badge variant="default" className="bg-green-500">
                {successCount} OK
              </Badge>
              {errorCount > 0 && (
                <Badge variant="destructive">{errorCount} Error</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Details */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Session Info</CardTitle>
            <CardDescription>Basic information</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Session ID</span>
              <span className="font-mono text-sm truncate max-w-[200px]">{sessionId}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">First Message</span>
              <span className="text-sm">
                {formatDate(messages[0]?.timestamp)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Last Message</span>
              <span className="text-sm">
                {formatDate(messages[messages.length - 1]?.timestamp)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Participants</CardTitle>
            <CardDescription>Users and bots involved</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <span className="text-muted-foreground text-sm">Users:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {(users as string[]).map((u: string) => (
                  <Badge key={u} variant="outline" className="text-xs">
                    {u.slice(0, 16)}...
                  </Badge>
                ))}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground text-sm">Bots:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {(bots as string[]).map((b: string) => (
                  <Badge key={b} variant="secondary">
                    {b}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Conversation Flow */}
      <Card>
        <CardHeader>
          <CardTitle>Conversation Flow</CardTitle>
          <CardDescription>
            {conversationPairs.length} exchanges
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {conversationPairs.map((pair, i) => (
            <div key={i} className="border rounded-lg p-4 space-y-3">
              {/* User Message */}
              {pair.user && (
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                    <User className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">
                        {pair.user.user_id?.slice(0, 16)}...
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(pair.user.timestamp)}
                      </span>
                      {pair.user.chat_type === "group" && (
                        <Badge variant="outline" className="text-xs">
                          Group
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm bg-blue-50 dark:bg-blue-950/50 rounded-lg p-3">
                      {pair.user.message}
                    </div>
                  </div>
                </div>
              )}

              {/* Assistant Response */}
              {pair.assistant && (
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{pair.assistant.bot_key || "assistant"}</span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(pair.assistant.timestamp)}
                      </span>
                      {pair.assistant.status === "success" ? (
                        <CheckCircle className="h-3 w-3 text-green-500" />
                      ) : (
                        <XCircle className="h-3 w-3 text-red-500" />
                      )}
                      <span className="text-xs text-muted-foreground">
                        {formatLatency(pair.assistant.latency_ms)}
                      </span>
                    </div>
                    {pair.assistant.status === "error" ? (
                      <div className="text-sm bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-lg p-3 text-red-600">
                        Error: {pair.assistant.error}
                      </div>
                    ) : (
                      <div className="text-sm bg-green-50 dark:bg-green-950/50 rounded-lg p-3 whitespace-pre-wrap">
                        {pair.assistant.response}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

        </CardContent>
      </Card>

      {/* Live WebSocket Messages (admin real-time) */}
      {wsMessages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">实时消息</CardTitle>
            <CardDescription>通过 WebSocket 实时接收</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {wsMessages.map((msg, i) => (
              <div key={i} className="flex gap-3">
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  msg.role === "user"
                    ? "bg-blue-100 dark:bg-blue-900"
                    : "bg-green-100 dark:bg-green-900"
                }`}>
                  {msg.role === "user"
                    ? <User className="h-4 w-4 text-blue-600" />
                    : <Bot className="h-4 w-4 text-green-600" />
                  }
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium mb-1">
                    {msg.role === "user" ? "You" : "Claude"}
                  </div>
                  <div className={`text-sm rounded-lg p-3 whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "bg-blue-50 dark:bg-blue-950/50"
                      : "bg-green-50 dark:bg-green-950/50"
                  }`}>
                    {msg.content}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </CardContent>
        </Card>
      )}

      {/* Message Input */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">发送消息</CardTitle>
          <CardDescription>向 Claude 发送新消息（仅限 admin 会话）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="输入消息，按 Enter 发送..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isSending}
              className="flex-1"
            />
            <Button onClick={handleSend} disabled={isSending || !inputMessage.trim()}>
              {isSending ? (
                <span className="animate-spin">
                  <Clock className="h-4 w-4" />
                </span>
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function SessionDetailLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-64" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
      <Skeleton className="h-96" />
    </div>
  )
}

function SessionDetailPage() {
  return (
    <Suspense fallback={<SessionDetailLoading />}>
      <SessionDetailContent />
    </Suspense>
  )
}
