import type { MeterType } from './types';

export const METER_TYPE_LABELS: Record<MeterType, string> = {
  cold_water: 'Cold Water',
  hot_water: 'Hot Water',
  electricity: 'Electricity',
};

export const METER_TYPE_COLORS: Record<MeterType, string> = {
  cold_water: 'bg-info text-info-foreground',
  hot_water: 'bg-warning text-warning-foreground',
  electricity: 'bg-chart-1 text-white',
};

export const METER_TYPE_CHART_COLORS: Record<MeterType, string> = {
  cold_water: '#0ea5e9',
  hot_water: '#f59e0b',
  electricity: '#3b82f6',
};
