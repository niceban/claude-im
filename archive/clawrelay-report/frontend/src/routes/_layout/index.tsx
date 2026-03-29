import { createFileRoute } from "@tanstack/react-router"
import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"
import useAuth from "@/hooks/useAuth"
import { MetricsService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  MessageSquare,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  Bot,
  Users,
} from "lucide-react"
import { DailyTrendChart } from "@/components/ui/charts"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - Clawrelay Report",
      },
    ],
  }),
})

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

function DashboardLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-9 w-64 mb-2" />
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Skeleton className="col-span-2 h-48" />
        <Skeleton className="h-48" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
    </div>
  )
}

function DashboardContent() {
  const { user: currentUser } = useAuth()

  const { data: stats } = useSuspenseQuery({
    queryFn: () =>
      MetricsService.readChatStatistics({}) as unknown as Promise<ChatStats>,
    queryKey: ["chat-statistics"],
  })

  const formatLatency = (ms: number) => {
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  const todayStats = stats.by_date?.[0]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Hi, {currentUser?.full_name || currentUser?.email} 👋
        </h1>
        <p className="text-muted-foreground">
          Clawrelay Report Dashboard · {stats.total_conversations} conversations tracked
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Conversations</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_conversations}</div>
            <p className="text-xs text-muted-foreground">
              {todayStats ? `+${todayStats.count} today` : "No activity today"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.success_rate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">
              {stats.success_count} successful · {stats.error_count} failed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatLatency(stats.avg_latency_ms)}</div>
            <p className="text-xs text-muted-foreground">
              P95 latency: {formatLatency(stats.max_latency_ms || 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Bots</CardTitle>
            <Bot className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.by_bot?.length || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats.by_user?.length || 0} unique users
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Activity + Users Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Daily Activity */}
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Daily Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DailyTrendChart data={(stats.by_date || []).slice(0, 7)} height={260} />
            <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-green-500" />
                Success
              </span>
              <span className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-secondary" />
                Total
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Recent Errors */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              Recent Errors
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats.recent_errors && stats.recent_errors.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_errors.slice(0, 5).map((err, i) => (
                  <div key={i} className="text-xs">
                    <div className="flex items-start gap-2">
                      <Badge variant="destructive" className="mt-0.5 text-[10px] px-1 py-0">
                        ERR
                      </Badge>
                      <div className="flex-1 min-w-0">
                        <p className="text-muted-foreground truncate">{err.error}</p>
                        <p className="text-[10px] text-muted-foreground/60">
                          {err.message?.slice(0, 30)}...
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No errors recorded</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Users + Bots */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              Top Users
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(stats.by_user || []).slice(0, 5).map((u) => (
                <div key={u.user_id} className="flex items-center justify-between text-sm">
                  <span className="font-mono text-xs text-muted-foreground truncate max-w-[200px]">
                    {u.user_id.slice(0, 20)}...
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="font-mono">{u.count}</span>
                    <Badge
                      variant="outline"
                      className={`text-xs ${
                        u.error === 0
                          ? "text-green-600"
                          : u.success > u.error
                            ? "text-yellow-600"
                            : "text-red-600"
                      }`}
                    >
                      {u.success}/{u.error} err
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-4 w-4" />
              Bot Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(stats.by_bot || []).map((b) => (
                <div key={b.bot_key}>
                  <div className="flex items-center justify-between mb-1">
                    <Badge variant="secondary">{b.bot_key}</Badge>
                    <span className="text-sm font-mono">{b.count}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-secondary overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{
                        width: `${(b.count / stats.total_conversations) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Last Updated */}
      <div className="text-xs text-muted-foreground text-center">
        Last updated: {stats.last_updated
          ? new Date(stats.last_updated).toLocaleString("zh-CN")
          : "N/A"}
      </div>
    </div>
  )
}

function Dashboard() {
  return (
    <Suspense fallback={<DashboardLoading />}>
      <DashboardContent />
    </Suspense>
  )
}
