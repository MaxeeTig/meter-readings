import { useRef, useState } from 'react';
import { Camera, FileCheck, Loader2, Upload, X } from 'lucide-react';
import { toast } from 'sonner';
import type { ApiOcrDraftResponse, MeterType, OCRResult } from '../types';
import { METER_TYPE_LABELS } from '../constants';

interface UploadOCRProps {
  onSave: (payload: {
    draftId: string;
    meterType: MeterType;
    value: number;
    capturedAt: string;
  }) => Promise<void>;
}

export function UploadOCR({ onSave }: UploadOCRProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null);
  const [formData, setFormData] = useState({
    meterType: '' as MeterType | '',
    value: '',
    datetime: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    if (!file.type.match(/image\/(jpeg|jpg|png|webp|heic)/)) {
      setErrors({ file: 'Please select a valid image file (JPG, PNG, WEBP, or HEIC)' });
      return;
    }

    setSelectedFile(file);
    setErrors({});

    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const toDatetimeLocal = (iso: string) => {
    const dt = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
  };

  const handleRecognize = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setErrors({});

    try {
      const form = new FormData();
      form.append('file', selectedFile);

      const response = await fetch('/api/ocr', {
        method: 'POST',
        body: form,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const message = typeof err?.detail === 'string' ? err.detail : 'OCR failed';
        throw new Error(message);
      }

      const data = (await response.json()) as ApiOcrDraftResponse;
      const parsed: OCRResult = {
        draftId: data.draft_id,
        meterType: data.meter_type,
        value: data.value,
        confidence: data.confidence,
        capturedAt: data.captured_at,
        sourceDate: data.source_date,
        filenameOriginal: data.filename_original,
        rawText: data.raw_text,
      };
      setOcrResult(parsed);
      setFormData({
        meterType: parsed.meterType,
        value: parsed.value.toString(),
        datetime: toDatetimeLocal(parsed.capturedAt),
      });
      toast.success('OCR completed');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'OCR failed';
      setErrors({ file: message });
      toast.error(message);
    } finally {
      setIsProcessing(false);
    }
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!ocrResult) {
      newErrors.file = 'Run OCR before saving';
    }
    if (!formData.meterType) {
      newErrors.meterType = 'Meter type is required';
    }
    if (!formData.value) {
      newErrors.value = 'Reading value is required';
    } else if (isNaN(Number(formData.value)) || Number(formData.value) < 0) {
      newErrors.value = 'Please enter a valid non-negative number';
    }
    if (!formData.datetime) {
      newErrors.datetime = 'Date and time are required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate() || !ocrResult) return;

    setIsSaving(true);
    try {
      await onSave({
        draftId: ocrResult.draftId,
        meterType: formData.meterType as MeterType,
        value: Number(formData.value),
        capturedAt: new Date(formData.datetime).toISOString(),
      });
      toast.success('Reading saved');
      handleReset();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save';
      toast.error(message);
      setErrors({ file: message });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPreview('');
    setOcrResult(null);
    setFormData({
      meterType: '',
      value: '',
      datetime: '',
    });
    setErrors({});
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (cameraInputRef.current) {
      cameraInputRef.current.value = '';
    }
  };

  return (
    <div className="bg-card rounded-[14px] shadow-[0_4px_14px_rgba(15,23,42,0.08)] p-6">
      <h2 className="mb-4">Upload & Verify</h2>

      {!selectedFile ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-[14px] p-8 text-center transition-colors ${
            isDragging
              ? 'border-primary bg-accent'
              : 'border-border bg-input-background hover:border-primary/50'
          }`}
        >
          <div className="flex flex-col items-center gap-4">
            <button
              type="button"
              onClick={() => cameraInputRef.current?.click()}
              className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center hover:bg-primary/20 transition-colors cursor-pointer"
              aria-label="Open camera"
            >
              <Camera className="w-8 h-8 text-primary" />
            </button>
            <div>
              <p className="text-foreground mb-1">Drop photo here or</p>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-[10px] hover:bg-primary/90 transition-colors min-h-[44px]"
              >
                <Upload className="w-5 h-5" />
                Choose Photo
              </button>
            </div>
            <p className="text-xs text-muted-foreground">Accepted: JPG, JPEG, PNG, WEBP, HEIC</p>
          </div>
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp,image/heic"
            capture="environment"
            onChange={handleFileChange}
            className="hidden"
          />
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp,image/heic"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
      ) : (
        <>
          <div className="space-y-4">
            <div className="relative inline-block">
              <img
                src={preview}
                alt="Meter preview"
                className="w-32 h-32 object-cover rounded-[10px] border border-border"
              />
              <button
                type="button"
                onClick={handleReset}
                className="absolute -top-2 -right-2 w-6 h-6 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center hover:bg-destructive/90"
                aria-label="Remove photo"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {!ocrResult && (
              <button
                type="button"
                onClick={handleRecognize}
                disabled={isProcessing}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-[10px] hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Recognizing...
                  </>
                ) : (
                  <>
                    <FileCheck className="w-5 h-5" />
                    Recognize
                  </>
                )}
              </button>
            )}
          </div>

          {ocrResult && (
            <div className="mt-6 p-4 bg-accent/30 border border-accent-foreground/20 rounded-[10px]" role="status" aria-live="polite">
              <p className="text-sm text-accent-foreground">
                OCR: {Math.round(ocrResult.confidence * 100)}% confidence. Source date: {ocrResult.sourceDate}.
              </p>
              <p className="text-xs text-muted-foreground mt-1">{ocrResult.rawText}</p>
            </div>
          )}

          {ocrResult && (
            <form className="mt-6 space-y-4">
              {Object.keys(errors).length > 0 && (
                <div className="p-4 bg-destructive/10 border border-destructive rounded-[10px]" role="alert">
                  <p className="text-sm text-destructive">Please fix the following errors:</p>
                  <ul className="mt-1 text-sm text-destructive list-disc list-inside">
                    {Object.values(errors).map((error, i) => (
                      <li key={i}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <label htmlFor="meterType" className="block mb-2">
                  Meter Type *
                </label>
                <select
                  id="meterType"
                  value={formData.meterType}
                  onChange={(e) => setFormData({ ...formData, meterType: e.target.value as MeterType })}
                  className={`w-full px-4 py-3 bg-input-background border rounded-[10px] min-h-[44px] ${
                    errors.meterType ? 'border-destructive' : 'border-border'
                  }`}
                >
                  <option value="" disabled>
                    Select meter type
                  </option>
                  {Object.entries(METER_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="value" className="block mb-2">
                  Reading Value *
                </label>
                <input
                  id="value"
                  type="number"
                  step="0.00001"
                  value={formData.value}
                  onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                  className={`w-full px-4 py-3 bg-input-background border rounded-[10px] min-h-[44px] ${
                    errors.value ? 'border-destructive' : 'border-border'
                  }`}
                />
              </div>

              <div>
                <label htmlFor="datetime" className="block mb-2">
                  Date & Time *
                </label>
                <input
                  id="datetime"
                  type="datetime-local"
                  value={formData.datetime}
                  onChange={(e) => setFormData({ ...formData, datetime: e.target.value })}
                  className={`w-full px-4 py-3 bg-input-background border rounded-[10px] min-h-[44px] ${
                    errors.datetime ? 'border-destructive' : 'border-border'
                  }`}
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex-1 sm:flex-initial px-6 py-3 bg-primary text-primary-foreground rounded-[10px] hover:bg-primary/90 transition-colors min-h-[44px] disabled:opacity-60"
                >
                  {isSaving ? 'Saving...' : 'Save Reading'}
                </button>
                <button
                  type="button"
                  onClick={handleReset}
                  className="flex-1 sm:flex-initial px-6 py-3 bg-secondary text-secondary-foreground rounded-[10px] hover:bg-secondary/90 transition-colors min-h-[44px]"
                >
                  Reset
                </button>
              </div>
            </form>
          )}
        </>
      )}

      {errors.file && (
        <div className="mt-4 p-4 bg-destructive/10 border border-destructive rounded-[10px]" role="alert">
          <p className="text-sm text-destructive">{errors.file}</p>
        </div>
      )}
    </div>
  );
}
