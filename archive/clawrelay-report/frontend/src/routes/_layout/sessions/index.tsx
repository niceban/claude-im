import React from "react"
import { useSuspenseQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { Bot, Clock, Plus, User } from "lucide-react"
import { Suspense } from "react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { SessionTimelineChart } from "@/components/ui/charts"

interface Session {
  session_id: string
  user: string
  bot_key: string
  status: "running" | "completed" | "error"
  created_at: string
  last_active: string
  input_tokens?: number
  output_tokens?: number
}

interface SessionsResponse {
  sessions: Session[]
  total: number
  page: number
  limit: number
  timestamp?: string
}

const statusColors = {
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
}

const statusLabels = {
  running: "Running",
  completed: "Completed",
  error: "Error",
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "N/A"
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

export const Route = createFileRoute("/_layout/sessions/")({
  component: SessionsPage,
  head: () => ({
    meta: [{ title: "Sessions - Clawrelay Report" }],
  }),
})

function SessionsContent() {
  const [statusFilter, setStatusFilter] = React.useState<string>("all")
  const [page, setPage] = React.useState(1)
  const [newSessionOpen, setNewSessionOpen] = React.useState(false)
  const [newSessionMessage, setNewSessionMessage] = React.useState("")
  const [isCreating, setIsCreating] = React.useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const PAGE_SIZE = 20

  const { data: sessionsData } = useSuspenseQuery({
    queryFn: () => MetricsService.readSessions({ page, limit: PAGE_SIZE }),
    queryKey: ["sessions", page],
    refetchInterval: 30000,
  })

  const sessions = (sessionsData as unknown as SessionsResponse)?.sessions || []
  const total = (sessionsData as unknown as SessionsResponse)?.total || 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const filteredSessions =
    statusFilter === "all"
      ? sessions
      : sessions.filter((s) => s.status === statusFilter)

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
        setNewSessionOpen(false)
        setNewSessionMessage("")
        queryClient.invalidateQueries({ queryKey: ["sessions"] })
        if (data.relay_session_id) {
          navigate({ to: "/sessions/$sessionId", params: { sessionId: data.relay_session_id } })
        }
      }
    } finally {
      setIsCreating(false)
    }
  }

  // Aggregate sessions by hour for timeline chart
  const hourlyData = React.useMemo(() => {
    const hourCounts: Record<string, number> = {}
    sessions.forEach((session) => {
      if (session.created_at) {
        const hour = new Date(session.created_at).getHours()
        const hourKey = `${hour.toString().padStart(2, "0")}:00`
        hourCounts[hourKey] = (hourCounts[hourKey] || 0) + 1
      }
    })
    return Object.entries(hourCounts)
      .map(([hour, count]) => ({ hour, count }))
      .sort((a, b) => a.hour.localeCompare(b.hour))
  }, [sessions])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Sessions</h1>
          <p className="text-muted-foreground">
            Active and historical sessions ({total} total)
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Dialog open={newSessionOpen} onOpenChange={setNewSessionOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-1" />
                新建会话
              </Button>
            </DialogTrigger>
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
                  className="w-full"
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setNewSessionOpen(false)} disabled={isCreating}>
                  取消
                </Button>
                <Button onClick={handleCreateSession} disabled={isCreating}>
                  {isCreating ? "创建中..." : "创建并发送"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1) }}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="running">Running</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Session Timeline Chart */}
      {hourlyData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Sessions by Hour
            </CardTitle>
            <CardDescription>Distribution of session creation times</CardDescription>
          </CardHeader>
          <CardContent>
            <SessionTimelineChart data={hourlyData} dataKey="hour" height={200} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Session List</CardTitle>
          <CardDescription>Click a row to view session details</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Session ID</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Bot</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Last Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSessions.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center h-32 text-muted-foreground"
                  >
                    No sessions found
                  </TableCell>
                </TableRow>
              ) : (
                filteredSessions.map((session) => (
                  <TableRow
                    key={session.session_id}
                    className="cursor-pointer hover:bg-muted/50"
                  >
                    <TableCell className="font-mono text-xs">
                      <Link
                        to="/sessions/$sessionId"
                        params={{ sessionId: session.session_id }}
                        className="hover:underline"
                      >
                        {session.session_id.slice(0, 8)}...
                      </Link>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="truncate max-w-[120px]">
                          {session.user || "Unknown"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Bot className="h-4 w-4 text-muted-foreground" />
                        <span className="truncate max-w-[100px]">
                          {session.bot_key || "Unknown"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={statusColors[session.status] || ""}>
                        {statusLabels[session.status] || session.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm">
                          {formatDate(session.created_at)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">
                        {formatDate(session.last_active)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {Math.min((page - 1) * PAGE_SIZE + 1, total)} to{" "}
                {Math.min(page * PAGE_SIZE, total)} of {total} sessions
              </p>
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      className={page <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                    />
                  </PaginationItem>
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum: number
                    if (totalPages <= 5) {
                      pageNum = i + 1
                    } else if (page <= 3) {
                      pageNum = i + 1
                    } else if (page >= totalPages - 2) {
                      pageNum = totalPages - 4 + i
                    } else {
                      pageNum = page - 2 + i
                    }
                    return (
                      <PaginationItem key={pageNum}>
                        <PaginationLink
                          isActive={page === pageNum}
                          onClick={() => setPage(pageNum)}
                          className="cursor-pointer"
                        >
                          {pageNum}
                        </PaginationLink>
                      </PaginationItem>
                    )
                  })}
                  <PaginationItem>
                    <PaginationNext
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      className={page >= totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function SessionsLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-32" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32 mb-2" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function SessionsPage() {
  return (
    <Suspense fallback={<SessionsLoading />}>
      <SessionsContent />
    </Suspense>
  )
}
