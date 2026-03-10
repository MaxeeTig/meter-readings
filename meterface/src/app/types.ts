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

export interface MosenergosbytOtpMethod {
  kd_tfa: number;
  nm_tfa: string;
  pr_active: boolean | null;
  nn_contact: string | null;
}

export interface MosenergosbytStatus {
  authorized: boolean;
  otp_required: boolean;
  has_device_token: boolean;
  authorized_at: string | null;
  otp_methods: MosenergosbytOtpMethod[];
  selected_kd_tfa: number | null;
}

export interface MosenergosbytMeter {
  meter_type: MeterType | null;
  nm_counter: string | null;
  vl_last_indication: number | null;
  dt_last_indication: string | null;
  id_abonent: number | string | null;
  id_counter: number | string | null;
  id_service: number | string | null;
}

export interface ApiMosenergosbytMetersResponse {
  meters: MosenergosbytMeter[];
}
