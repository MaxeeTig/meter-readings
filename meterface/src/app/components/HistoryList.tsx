import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import type { MeterReading } from '../types';
import { METER_TYPE_COLORS, METER_TYPE_LABELS } from '../constants';

interface HistoryListProps {
  readings: MeterReading[];
  onRefresh: () => void;
  isLoading?: boolean;
}

function latestMonthRows(readings: MeterReading[]): MeterReading[] {
  if (!readings.length) {
    return [];
  }
  const latest = new Date(readings[0].datetime);
  const y = latest.getFullYear();
  const m = latest.getMonth();
  return readings.filter((r) => {
    const dt = new Date(r.datetime);
    return dt.getFullYear() === y && dt.getMonth() === m;
  });
}

export function HistoryList({ readings, onRefresh, isLoading = false }: HistoryListProps) {
  const [showAll, setShowAll] = useState(false);

  const monthRows = useMemo(() => latestMonthRows(readings), [readings]);
  const hasMore = monthRows.length < readings.length;
  const visible = showAll || !hasMore ? readings : monthRows;

  const formatDateTime = (datetime: string) => {
    const date = new Date(datetime);
    return date.toLocaleString('ru-RU', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="bg-card rounded-[14px] shadow-[0_4px_14px_rgba(15,23,42,0.08)] p-6">
      <div className="flex items-center justify-between mb-4">
        <h2>Reading History</h2>
        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-3 py-2 text-sm text-primary hover:bg-accent rounded-[10px] transition-colors min-h-[44px]"
          aria-label="Refresh readings"
        >
          <RefreshCw className="w-4 h-4" />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading readings...</div>
      ) : readings.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No readings yet. Add your first photo above.</p>
        </div>
      ) : (
        <>
          <div className="block lg:hidden space-y-3">
            {visible.map((reading) => (
              <div key={reading.id} className="p-4 bg-input-background border border-border rounded-[10px]">
                <div className="flex items-start justify-between mb-2">
                  <span className={`inline-block px-3 py-1 rounded-full text-sm ${METER_TYPE_COLORS[reading.meterType]}`}>
                    {METER_TYPE_LABELS[reading.meterType]}
                  </span>
                  <span className="text-xs text-muted-foreground uppercase">{reading.source}</span>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between items-baseline">
                    <span className="text-sm text-muted-foreground">Value:</span>
                    <span className="text-lg">
                      {reading.value.toFixed(2)} {reading.unit}
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground">{formatDateTime(reading.datetime)}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="hidden lg:block overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-sm text-muted-foreground">Date & Time</th>
                  <th className="text-left py-3 px-4 text-sm text-muted-foreground">Meter Type</th>
                  <th className="text-right py-3 px-4 text-sm text-muted-foreground">Value</th>
                  <th className="text-center py-3 px-4 text-sm text-muted-foreground">Source</th>
                  <th className="text-center py-3 px-4 text-sm text-muted-foreground">OCR</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((reading) => (
                  <tr key={reading.id} className="border-b border-border last:border-0">
                    <td className="py-3 px-4 text-sm">{formatDateTime(reading.datetime)}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-3 py-1 rounded-full text-xs ${METER_TYPE_COLORS[reading.meterType]}`}>
                        {METER_TYPE_LABELS[reading.meterType]}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {reading.value.toFixed(2)} {reading.unit}
                    </td>
                    <td className="py-3 px-4 text-center text-xs text-muted-foreground uppercase">{reading.source}</td>
                    <td className="py-3 px-4 text-center text-xs text-muted-foreground">
                      {(reading.confidence * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <div className="pt-4">
              <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-[10px] hover:bg-secondary/90 transition-colors"
              >
                {showAll ? (
                  <>
                    <ChevronUp className="w-4 h-4" />
                    Show latest month only
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" />
                    Show full history
                  </>
                )}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
