import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle,
  Clock,
  MessageSquare,
  Users,
  XCircle,
} from "lucide-react"
import { Suspense, useState } from "react"

import { MetricsService } from "@/client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

// Type definitions for chat statistics
interface ChatStats {
  total_conversations: number
  total_messages: number
  success_count: number
  error_count: number
  avg_latency_ms: number
  total_latency_ms: number
  min_latency_ms: number
  max_latency_ms: number
  success_rate: number
  error_rate: number
  by_date: Array<{ date: string; count: number; success: number; error: number; latency_sum: number; avg_latency?: number }>
  by_user: Array<{ user_id: string; count: number; success: number; error: number }>
  by_bot: Array<{ bot_key: string; count: number; success: number; error: number }>
  recent_errors: Array<{ timestamp: string; user_id: string; error: string; message: string }>
  last_updated: string
}

interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon: React.ElementType
  variant?: "default" | "success" | "error"
}

function StatCard({ title, value, description, icon: Icon, variant = "default" }: StatCardProps) {
  const variantClasses = {
    default: "",
    success: "border-green-500/50",
    error: "border-red-500/50",
  }

  return (
    <Card className={variantClasses[variant]}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </CardContent>
    </Card>
  )
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M"
  if (n >= 1000) return (n / 1000).toFixed(1) + "K"
  return n.toLocaleString()
}

function formatLatency(ms: number): string {
  if (ms >= 60000) return (ms / 60000).toFixed(1) + " min"
  if (ms >= 1000) return (ms / 1000).toFixed(1) + " s"
  return ms + " ms"
}

export const Route = createFileRoute("/_layout/metrics")({
  component: Metrics,
  head: () => ({
    meta: [{ title: "Metrics - Clawrelay Report" }],
  }),
})

function MetricsContent() {
  const [selectedBot, setSelectedBot] = useState<string>("all")
  const [selectedPeriod, setSelectedPeriod] = useState<string>("all")

  const { data: stats } = useSuspenseQuery({
    queryFn: () => MetricsService.readChatStatistics({}) as unknown as Promise<ChatStats>,
    queryKey: ["chat-statistics"],
    refetchInterval: 30000,
  })

  // Filter by bot
  const filteredByBot = selectedBot === "all"
    ? stats.by_bot as Array<any>
    : (stats.by_bot as Array<any>).filter((b: any) => b.bot_key === selectedBot)

  // Filter by period
  const filteredByPeriod = selectedPeriod === "all"
    ? stats.by_date as Array<any>
    : (stats.by_date as Array<any>).filter((d: any) => {
        if (selectedPeriod === "today") return d.date === new Date().toISOString().slice(0, 10)
        if (selectedPeriod === "7d") {
          const sevenDaysAgo = new Date()
          sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
          return d.date >= sevenDaysAgo.toISOString().slice(0, 10)
        }
        return true
      })

  // Calculate totals from filtered data
  const totalFiltered = filteredByPeriod.reduce((sum: number, d: any) => sum + d.count, 0)
  const successFiltered = filteredByPeriod.reduce((sum: number, d: any) => sum + d.success, 0)
  const errorFiltered = filteredByPeriod.reduce((sum: number, d: any) => sum + d.error, 0)
  const totalLatencyFiltered = filteredByPeriod.reduce((sum: number, d: any) => sum + d.latency_sum, 0)
  const avgLatencyFiltered = totalFiltered > 0 ? totalLatencyFiltered / totalFiltered : 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Metrics Dashboard</h1>
        <p className="text-muted-foreground">Real-time monitoring from chat history</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="w-48">
          <Select value={selectedBot} onValueChange={setSelectedBot}>
            <SelectTrigger>
              <SelectValue placeholder="All Bots" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Bots</SelectItem>
              {(stats.by_bot as Array<any>).map((b: any) => (
                <SelectItem key={b.bot_key} value={b.bot_key}>
                  {b.bot_key} ({b.count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-48">
          <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
            <SelectTrigger>
              <SelectValue placeholder="All Time" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Time</SelectItem>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Conversations"
          value={formatNumber(totalFiltered)}
          description={`${stats.total_conversations} all time`}
          icon={MessageSquare}
        />
        <StatCard
          title="Success Rate"
          value={`${stats.success_rate.toFixed(1)}%`}
          description={`${successFiltered} successful`}
          icon={CheckCircle}
          variant="success"
        />
        <StatCard
          title="Error Rate"
          value={`${stats.error_rate.toFixed(1)}%`}
          description={`${errorFiltered} failed`}
          icon={XCircle}
          variant={errorFiltered > 0 ? "error" : "default"}
        />
        <StatCard
          title="Avg Response Time"
          value={formatLatency(avgLatencyFiltered)}
          description={`Total: ${formatLatency(stats.total_latency_ms)}`}
          icon={Clock}
        />
      </div>

      {/* User Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="Unique Users"
          value={stats.by_user.length}
          description="In selected period"
          icon={Users}
        />
        <StatCard
          title="Avg Latency"
          value={formatLatency(stats.avg_latency_ms)}
          description="All time average"
          icon={Activity}
        />
        <StatCard
          title="Max Latency"
          value={formatLatency(stats.max_latency_ms)}
          description="Slowest response"
          icon={AlertTriangle}
        />
      </div>

      {/* Daily Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Daily Activity</CardTitle>
          <CardDescription>Conversations by date</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="text-right">Success</TableHead>
                <TableHead className="text-right">Error</TableHead>
                <TableHead className="text-right">Avg Latency</TableHead>
                <TableHead>Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredByPeriod.map((day: any) => (
                <TableRow key={day.date}>
                  <TableCell className="font-medium">{day.date}</TableCell>
                  <TableCell className="text-right">{day.count}</TableCell>
                  <TableCell className="text-right text-green-600">{day.success}</TableCell>
                  <TableCell className="text-right text-red-600">{day.error}</TableCell>
                  <TableCell className="text-right">{formatLatency(day.avg_latency || 0)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-green-500"
                          style={{ width: `${(day.success / day.count) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs">
                        {((day.success / day.count) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* By Bot */}
      <Card>
        <CardHeader>
          <CardTitle>By Bot</CardTitle>
          <CardDescription>Distribution across bots</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bot</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="text-right">Success</TableHead>
                <TableHead className="text-right">Error</TableHead>
                <TableHead>Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredByBot.map((bot: any) => (
                <TableRow key={bot.bot_key}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Bot className="h-4 w-4" />
                      <span className="font-medium">{bot.bot_key}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">{bot.count}</TableCell>
                  <TableCell className="text-right text-green-600">{bot.success}</TableCell>
                  <TableCell className="text-right text-red-600">{bot.error}</TableCell>
                  <TableCell>
                    <Badge
                      variant={bot.error === 0 ? "default" : "destructive"}
                    >
                      {((bot.success / bot.count) * 100).toFixed(1)}%
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Recent Errors */}
      {stats.recent_errors.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-red-600">Recent Errors</CardTitle>
            <CardDescription>Latest failed conversations</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stats.recent_errors.slice(0, 10).map((err: any, i: number) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs whitespace-nowrap">
                      {String(err.timestamp || "").slice(11, 19)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {String(err.user_id || "unknown").slice(0, 12)}...
                    </TableCell>
                    <TableCell>
                      <Badge variant="destructive" className="text-xs">
                        <AlertCircle className="h-3 w-3 mr-1" />
                        {String(err.error || "").slice(0, 30)}...
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-xs truncate">
                      {String(err.message || "")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Last Updated */}
      <div className="text-xs text-muted-foreground text-center">
        Last updated: {stats.last_updated}
      </div>
    </div>
  )
}

function MetricsLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-48 mb-2" />
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <Skeleton className="h-64" />
    </div>
  )
}

function Metrics() {
  return (
    <Suspense fallback={<MetricsLoading />}>
      <MetricsContent />
    </Suspense>
  )
}
