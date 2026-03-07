export type MeterType = 'cold_water' | 'hot_water' | 'electricity';

export interface MeterReading {
  id: string;
  meterType: MeterType;
  value: number;
  datetime: string;
  unit: string;
  confidence: number;
  sourceDate: 'exif' | 'filename' | 'server_time';
  filenameOriginal: string;
  source: 'ocr' | 'manual';
  savedAt: string;
}

export interface OCRResult {
  draftId: string;
  meterType: MeterType;
  value: number;
  confidence: number;
  capturedAt: string;
  sourceDate: 'exif' | 'filename' | 'server_time';
  filenameOriginal: string;
  rawText: string;
}

export interface ApiReadingRecord {
  id: string;
  captured_at: string;
  saved_at: string;
  meter_type: MeterType;
  value: number;
  unit: string;
  confidence: number;
  source_date: 'exif' | 'filename' | 'server_time';
  filename_original: string;
}

export interface ApiOcrDraftResponse {
  draft_id: string;
  meter_type: MeterType;
  value: number;
  unit: string;
  confidence: number;
  captured_at: string;
  source_date: 'exif' | 'filename' | 'server_time';
  filename_original: string;
  raw_text: string;
}
