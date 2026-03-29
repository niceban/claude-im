import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { AlertCircle, Bot, CheckCircle, MessageSquare, Search, User } from "lucide-react"
import { Suspense, useState } from "react"

import { MetricsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { DistributionPieChart } from "@/components/ui/charts"

// Type definitions for chat history
interface ChatHistoryResponse {
  results: Array<{
    timestamp: string
    bot_key: string
    user_id: string
    stream_id: string
    relay_session_id: string
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
  }>
  total: number
  page: number
  limit: number
}

// Type definitions for chat statistics
interface ChatStats {
  total_conversations: number
  total_messages: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  max_latency_ms: number
  success_rate: number
  error_rate: number
  by_date: Array<{
    date: string
    count: number
    success: number
    error: number
    avg_latency: number
  }>
  by_user: Array<{
    user_id: string
    count: number
    success: number
    error: number
  }>
  by_bot: Array<{
    bot_key: string
    count: number
    success: number
    error: number
  }>
  recent_errors: Array<{
    timestamp: string
    user_id: string
    error: string
    message: string
  }>
  last_updated: string
}

function formatDate(ts: string): string {
  if (!ts) return ""
  const d = new Date(ts)
  return d.toLocaleString()
}

function formatLatency(ms: number): string {
  if (ms >= 60000) return (ms / 60000).toFixed(1) + " min"
  if (ms >= 1000) return (ms / 1000).toFixed(1) + " s"
  return ms + " ms"
}

function truncate(str: string, len: number): string {
  if (!str) return ""
  return str.length > len ? str.slice(0, len) + "..." : str
}

export const Route = createFileRoute("/_layout/history")({
  component: History,
  head: () => ({
    meta: [{ title: "Chat History - Clawrelay Report" }],
  }),
})

function HistoryContent() {
  const navigate = useNavigate()
  const [query, setQuery] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [page, setPage] = useState(1)
  const limit = 20

  const { data, isLoading } = useSuspenseQuery({
    queryFn: () =>
      MetricsService.readChatHistory({
        q: searchQuery || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        page,
        limit,
      }) as unknown as Promise<ChatHistoryResponse>,
    queryKey: ["chat-history", searchQuery, statusFilter, page],
  })

  // Query for statistics (used for pie charts)
  const { data: stats } = useSuspenseQuery({
    queryFn: () =>
      MetricsService.readChatStatistics({}) as unknown as Promise<ChatStats>,
    queryKey: ["chat-statistics-for-history"],
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    setSearchQuery(query)
  }

  const totalPages = Math.ceil(data.total / limit)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Chat History</h1>
        <p className="text-muted-foreground">
          {data.total} conversations found
        </p>
      </div>

      {/* Search Form */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search messages..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="error">Error</SelectItem>
              </SelectContent>
            </Select>
            <Button type="submit">
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Distribution Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-4 w-4" />
              Bot Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DistributionPieChart
              data={(stats?.by_bot || []).map((b) => ({
                name: b.bot_key,
                value: b.count,
              }))}
              height={260}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-4 w-4" />
              User Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DistributionPieChart
              data={(stats?.by_user || []).map((u) => ({
                name: u.user_id.slice(0, 15),
                value: u.count,
              }))}
              height={260}
            />
          </CardContent>
        </Card>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : data.results.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <MessageSquare className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No conversations found</h3>
            <p className="text-muted-foreground">Try adjusting your search criteria</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Status</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Bot</TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead className="text-right">Latency</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.results.map((chat: any, i: number) => (
                    <TableRow
                      key={i}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => {
                        if (chat.relay_session_id) {
                          navigate({ to: "/sessions/$sessionId", params: { sessionId: chat.relay_session_id } })
                        }
                      }}
                    >
                      <TableCell>
                        {chat.status === "success" ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-red-500" />
                        )}
                      </TableCell>
                      <TableCell className="text-xs whitespace-nowrap">
                        {formatDate(chat.timestamp)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-xs">
                          <User className="h-3 w-3" />
                          {truncate(chat.user_id || "unknown", 12)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          <Bot className="h-3 w-3 mr-1" />
                          {chat.bot_key}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-md">
                        <div className="text-xs">
                          <div className="text-muted-foreground truncate">
                            <span className="text-foreground font-medium">Q:</span>{" "}
                            {truncate(chat.message, 60)}
                          </div>
                          {chat.response && (
                            <div className="text-muted-foreground truncate">
                              <span className="text-foreground font-medium">A:</span>{" "}
                              {truncate(chat.response, 60)}
                            </div>
                          )}
                          {chat.error && (
                            <div className="text-red-500 truncate">
                              Error: {truncate(chat.error, 60)}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        {formatLatency(chat.latency_ms || 0)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function HistoryLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-32" />
      </div>
      <Skeleton className="h-20" />
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    </div>
  )
}

function History() {
  return (
    <Suspense fallback={<HistoryLoading />}>
      <HistoryContent />
    </Suspense>
  )
}
