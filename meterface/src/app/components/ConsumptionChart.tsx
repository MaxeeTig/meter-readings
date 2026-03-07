import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useMemo, useState } from 'react';
import type { MeterReading, MeterType } from '../types';
import { METER_TYPE_CHART_COLORS, METER_TYPE_LABELS } from '../constants';

interface ConsumptionChartProps {
  readings: MeterReading[];
}

interface ChartDataPoint {
  monthKey: string;
  monthLabel: string;
  cold_water?: number;
  hot_water?: number;
  electricity?: number;
}

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

export function ConsumptionChart({ readings }: ConsumptionChartProps) {
  const [chartMode, setChartMode] = useState<'electricity' | 'water'>('electricity');

  const calculateMonthlyConsumption = () => {
    const byType: Record<MeterType, MeterReading[]> = {
      cold_water: [],
      hot_water: [],
      electricity: [],
    };

    readings.forEach((reading) => {
      byType[reading.meterType].push(reading);
    });

    Object.keys(byType).forEach((type) => {
      byType[type as MeterType].sort(
        (a, b) => new Date(a.datetime).getTime() - new Date(b.datetime).getTime()
      );
    });

    const points = new Map<string, ChartDataPoint>();

    Object.entries(byType).forEach(([type, rows]) => {
      let prevValue: number | null = null;
      for (const row of rows) {
        const delta = prevValue === null ? 0 : row.value - prevValue;
        const date = new Date(row.datetime);
        const key = monthKey(date);
        if (!points.has(key)) {
          points.set(key, {
            monthKey: key,
            monthLabel: date.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' }),
          });
        }
        const point = points.get(key)!;
        const current = point[type as MeterType] ?? 0;
        point[type as MeterType] = Number((current + delta).toFixed(5));
        prevValue = row.value;
      }
    });

    return Array.from(points.values()).sort((a, b) => a.monthKey.localeCompare(b.monthKey));
  };

  const data = useMemo(() => calculateMonthlyConsumption(), [readings]);
  const hasData = data.length > 0;

  const activeMeterTypes: MeterType[] =
    chartMode === 'electricity' ? ['electricity'] : (['cold_water', 'hot_water'] as MeterType[]);
  const hasModeData = data.some((point) =>
    activeMeterTypes.some((type) => point[type] !== undefined)
  );

  return (
    <div className="bg-card rounded-[14px] shadow-[0_4px_14px_rgba(15,23,42,0.08)] p-6">
      <h2 className="mb-6">Monthly Consumption</h2>
      <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setChartMode('electricity')}
          className={`px-4 py-2 rounded-[10px] transition-colors ${
            chartMode === 'electricity'
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary text-secondary-foreground hover:bg-secondary/90'
          }`}
        >
          Electricity
        </button>
        <button
          type="button"
          onClick={() => setChartMode('water')}
          className={`px-4 py-2 rounded-[10px] transition-colors ${
            chartMode === 'water'
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary text-secondary-foreground hover:bg-secondary/90'
          }`}
        >
          Water (Hot + Cold)
        </button>
      </div>

      {!hasData || !hasModeData ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">
            Not enough data for this chart mode yet.
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis
              dataKey="monthLabel"
              stroke="var(--color-muted-foreground)"
              style={{ fontSize: '12px' }}
            />
            <YAxis stroke="var(--color-muted-foreground)" style={{ fontSize: '12px' }} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                fontSize: '14px',
              }}
              labelStyle={{ color: 'var(--color-foreground)' }}
            />
            <Legend
              wrapperStyle={{ paddingTop: '20px', fontSize: '14px' }}
              formatter={(value) => METER_TYPE_LABELS[value as MeterType]}
            />
            {activeMeterTypes.map((type) => (
              <Bar
                key={type}
                dataKey={type}
                fill={METER_TYPE_CHART_COLORS[type]}
                radius={[6, 6, 0, 0]}
                name={type}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
