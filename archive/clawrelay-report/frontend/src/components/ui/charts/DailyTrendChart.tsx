import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"

interface DailyTrendData {
  date: string
  count: number
  success: number
  error: number
}

interface DailyTrendChartProps {
  data: DailyTrendData[]
  height?: number
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
}

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-background border rounded-lg p-3 shadow-lg">
        <p className="font-medium mb-1">{formatDate(label)}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    )
  }
  return null
}

export function DailyTrendChart({ data, height = 280 }: DailyTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={{ fontSize: 12 }}
          className="text-muted-foreground"
        />
        <YAxis tick={{ fontSize: 12 }} className="text-muted-foreground" />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Line
          type="monotone"
          dataKey="count"
          name="Total"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--primary))", strokeWidth: 0, r: 3 }}
          activeDot={{ r: 5 }}
        />
        <Line
          type="monotone"
          dataKey="success"
          name="Success"
          stroke="#22c55e"
          strokeWidth={2}
          dot={{ fill: "#22c55e", strokeWidth: 0, r: 3 }}
          activeDot={{ r: 5 }}
        />
        {data.some((d) => d.error > 0) && (
          <Line
            type="monotone"
            dataKey="error"
            name="Error"
            stroke="#ef4444"
            strokeWidth={2}
            dot={{ fill: "#ef4444", strokeWidth: 0, r: 3 }}
            activeDot={{ r: 5 }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}
