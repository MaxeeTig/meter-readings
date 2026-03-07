import { useEffect, useState } from 'react';
import { toast, Toaster } from 'sonner';
import { Header } from './components/Header';
import { UploadOCR } from './components/UploadOCR';
import { HistoryList } from './components/HistoryList';
import { ConsumptionChart } from './components/ConsumptionChart';
import type { ApiReadingRecord, MeterReading, MeterType } from './types';

interface SaveReadingPayload {
  draftId: string;
  meterType: MeterType;
  value: number;
  capturedAt: string;
}

function mapApiReading(row: ApiReadingRecord): MeterReading {
  return {
    id: row.id,
    meterType: row.meter_type,
    value: row.value,
    datetime: row.captured_at,
    unit: row.unit,
    confidence: row.confidence,
    sourceDate: row.source_date,
    filenameOriginal: row.filename_original,
    source: row.source_date === 'server_time' ? 'manual' : 'ocr',
    savedAt: row.saved_at,
  };
}

function App() {
  const [readings, setReadings] = useState<MeterReading[]>([]);
  const [isOnline, setIsOnline] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  const loadReadings = async () => {
    try {
      setIsLoadingHistory(true);
      const response = await fetch('/api/readings');
      if (!response.ok) {
        throw new Error('Failed to load readings');
      }
      const rows = (await response.json()) as ApiReadingRecord[];
      const mapped = rows
        .map(mapApiReading)
        .sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime());
      setReadings(mapped);
      setIsOnline(true);
    } catch (error) {
      console.error(error);
      setIsOnline(false);
      toast.error('Failed to load readings');
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadReadings();
  }, []);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleSaveReading = async (payload: SaveReadingPayload) => {
    const response = await fetch('/api/readings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        draft_id: payload.draftId,
        meter_type: payload.meterType,
        value: payload.value,
        captured_at: payload.capturedAt,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      const message = typeof err?.detail === 'string' ? err.detail : 'Failed to save reading';
      throw new Error(message);
    }

    const saved = mapApiReading((await response.json()) as ApiReadingRecord);
    setReadings((prev) =>
      [saved, ...prev].sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime())
    );
  };

  const handleRefresh = async () => {
    await loadReadings();
    toast.info('Readings refreshed');
  };

  return (
    <div className="min-h-screen bg-background">
      <Header online={isOnline} />

      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="lg:hidden space-y-6">
          <UploadOCR onSave={handleSaveReading} />
          <HistoryList readings={readings} onRefresh={handleRefresh} isLoading={isLoadingHistory} />
          <ConsumptionChart readings={readings} />
        </div>

        <div className="hidden lg:block space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <UploadOCR onSave={handleSaveReading} />
            <div className="space-y-6">
              <HistoryList readings={readings} onRefresh={handleRefresh} isLoading={isLoadingHistory} />
            </div>
          </div>
          <ConsumptionChart readings={readings} />
        </div>
      </main>

      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
