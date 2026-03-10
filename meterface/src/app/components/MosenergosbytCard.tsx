import { useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { METER_TYPE_LABELS } from '../constants';
import type {
  MosenergosbytMeter,
  MosenergosbytStatus,
  MosenergosbytOtpMethod,
} from '../types';

interface MosenergosbytCardProps {
  status: MosenergosbytStatus | null;
  meters: MosenergosbytMeter[];
  isLoading: boolean;
  onStatusRefresh: () => Promise<void>;
  onMetersRefresh: () => Promise<void>;
}

const OTP_METHOD_LABELS: Record<number, string> = {
  1: 'Flash call',
  2: 'SMS',
  3: 'E-mail',
};

function defaultDeviceInfo(): string {
  return JSON.stringify({
    appver: '1.42.0',
    type: 'browser',
    userAgent: navigator.userAgent,
  });
}

function formatLastReadingDate(value: string | null): string {
  if (!value) return 'n/a';
  const normalized = value.replace(' ', 'T');
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function MosenergosbytCard({
  status,
  meters,
  isLoading,
  onStatusRefresh,
  onMetersRefresh,
}: MosenergosbytCardProps) {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [selectedKdTfa, setSelectedKdTfa] = useState<number>(2);
  const [showOtpMethodConfig, setShowOtpMethodConfig] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const otpMethods = status?.otp_methods ?? [];
  const effectiveKdTfa = status?.selected_kd_tfa ?? selectedKdTfa;

  const otpMethodOptions = useMemo(() => {
    if (otpMethods.length > 0) {
      return otpMethods;
    }
    const fallback: MosenergosbytOtpMethod[] = [
      { kd_tfa: 1, nm_tfa: 'flashcall', pr_active: true, nn_contact: null },
      { kd_tfa: 2, nm_tfa: 'sms', pr_active: true, nn_contact: null },
      { kd_tfa: 3, nm_tfa: 'e-mail', pr_active: true, nn_contact: null },
    ];
    return fallback;
  }, [otpMethods]);

  const handleLogin = async () => {
    if (!login || !password) {
      toast.error('Login and password are required');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch('/api/providers/mosenergosbyt/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login,
          password,
          vl_device_info: defaultDeviceInfo(),
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const message = typeof err?.detail === 'string' ? err.detail : 'Portal authorization failed';
        throw new Error(message);
      }

      const nextStatus = (await response.json()) as MosenergosbytStatus;
      if (nextStatus.otp_required) {
        const method = nextStatus.selected_kd_tfa ?? 2;
        setSelectedKdTfa(method);
        const otpResponse = await fetch('/api/providers/mosenergosbyt/otp/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kd_tfa: method }),
        });
        if (!otpResponse.ok) {
          const err = await otpResponse.json().catch(() => ({}));
          const message = typeof err?.detail === 'string' ? err.detail : 'Failed to send OTP';
          throw new Error(message);
        }
        toast.info('OTP code sent');
      } else {
        toast.success('Portal connected');
        await onMetersRefresh();
      }
      await onStatusRefresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Portal authorization failed';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSendOtp = async (kdTfa: number) => {
    setIsSubmitting(true);
    try {
      const response = await fetch('/api/providers/mosenergosbyt/otp/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kd_tfa: kdTfa }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const message = typeof err?.detail === 'string' ? err.detail : 'Failed to send OTP';
        throw new Error(message);
      }
      setSelectedKdTfa(kdTfa);
      await onStatusRefresh();
      toast.info('OTP code sent');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send OTP';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (!login || !password || !otpCode) {
      toast.error('Login, password and OTP code are required');
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await fetch('/api/providers/mosenergosbyt/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login,
          password,
          vl_device_info: defaultDeviceInfo(),
          nn_tfa_code: otpCode,
          kd_tfa: effectiveKdTfa,
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const message = typeof err?.detail === 'string' ? err.detail : 'Failed to verify OTP';
        throw new Error(message);
      }
      setOtpCode('');
      await onStatusRefresh();
      await onMetersRefresh();
      toast.success('Portal connected');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to verify OTP';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisconnect = async () => {
    setIsSubmitting(true);
    try {
      const response = await fetch('/api/providers/mosenergosbyt/disconnect', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to disconnect');
      }
      await onStatusRefresh();
      toast.info('Portal disconnected');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to disconnect';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const authorized = status?.authorized ?? false;
  const otpRequired = status?.otp_required ?? false;

  return (
    <div className="bg-card rounded-[14px] shadow-[0_4px_14px_rgba(15,23,42,0.08)] p-6">
      <div className="flex items-center justify-between gap-3">
        <h2>Mosenergosbyt</h2>
        {isLoading || isSubmitting ? <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" /> : null}
      </div>

      {!authorized && !otpRequired && (
        <div className="mt-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            Not connected to portal. Authorize to load provider meter readings.
          </p>

          <div className="space-y-3">
            <input
              type="text"
              placeholder="Portal login"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              className="w-full px-4 py-3 bg-input-background border border-border rounded-[10px] min-h-[44px]"
            />
            <input
              type="password"
              placeholder="Portal password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-input-background border border-border rounded-[10px] min-h-[44px]"
            />
            <button
              type="button"
              onClick={handleLogin}
              disabled={isSubmitting}
              className="w-full sm:w-auto px-6 py-3 bg-primary text-primary-foreground rounded-[10px] hover:bg-primary/90 transition-colors min-h-[44px] disabled:opacity-60"
            >
              Authorize
            </button>
          </div>
        </div>
      )}

      {otpRequired && (
        <div className="mt-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            OTP is required for this device. By default, code is sent via SMS.
          </p>

          <div className="space-y-3">
            <input
              type="text"
              placeholder="Portal login"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              className="w-full px-4 py-3 bg-input-background border border-border rounded-[10px] min-h-[44px]"
            />
            <input
              type="password"
              placeholder="Portal password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-input-background border border-border rounded-[10px] min-h-[44px]"
            />
            <input
              type="text"
              placeholder="OTP code"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value)}
              className="w-full px-4 py-3 bg-input-background border border-border rounded-[10px] min-h-[44px]"
            />
          </div>

          <button
            type="button"
            onClick={handleVerifyOtp}
            disabled={isSubmitting}
            className="w-full sm:w-auto px-6 py-3 bg-primary text-primary-foreground rounded-[10px] hover:bg-primary/90 transition-colors min-h-[44px] disabled:opacity-60"
          >
            Confirm OTP
          </button>

          <button
            type="button"
            onClick={() => setShowOtpMethodConfig((prev) => !prev)}
            className="block text-sm text-primary hover:underline"
          >
            {showOtpMethodConfig ? 'Hide OTP method' : 'Change OTP method'}
          </button>

          {showOtpMethodConfig && (
            <div className="space-y-2">
              <label className="block text-sm text-muted-foreground">OTP method</label>
              <select
                value={effectiveKdTfa}
                onChange={(e) => setSelectedKdTfa(Number(e.target.value))}
                className="w-full px-4 py-3 bg-input-background border border-border rounded-[10px] min-h-[44px]"
              >
                {otpMethodOptions.map((method) => (
                  <option key={method.kd_tfa} value={method.kd_tfa}>
                    {OTP_METHOD_LABELS[method.kd_tfa] ?? method.nm_tfa}
                    {method.nn_contact ? ` (${method.nn_contact})` : ''}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => handleSendOtp(effectiveKdTfa)}
                className="w-full sm:w-auto px-4 py-2 bg-secondary text-secondary-foreground rounded-[10px] hover:bg-secondary/90 transition-colors min-h-[44px]"
                disabled={isSubmitting}
              >
                Resend OTP
              </button>
            </div>
          )}
        </div>
      )}

      {authorized && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Connected. Meters auto-refresh every 5 minutes.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleDisconnect}
                className="px-4 py-2 bg-destructive text-destructive-foreground rounded-[10px] hover:bg-destructive/90 transition-colors min-h-[44px]"
              >
                Disconnect
              </button>
            </div>
          </div>

          {meters.length === 0 ? (
            <p className="text-sm text-muted-foreground">No portal water meters found.</p>
          ) : (
            <div className="space-y-3">
              {meters.map((meter, index) => {
                const meterLabel = meter.meter_type ? METER_TYPE_LABELS[meter.meter_type] : 'Unknown meter';
                return (
                  <div key={`${meter.id_counter ?? 'meter'}-${index}`} className="border border-border rounded-[10px] p-4">
                    <p className="text-sm text-muted-foreground">Meter label</p>
                    <p>{meterLabel}</p>

                    <p className="text-sm text-muted-foreground mt-3">nm_counter</p>
                    <p>{meter.nm_counter ?? 'n/a'}</p>

                    <p className="text-sm text-muted-foreground mt-3">vl_last_indication</p>
                    <p>{meter.vl_last_indication ?? 'n/a'}</p>

                    <p className="text-sm text-muted-foreground mt-3">dt_last_indication</p>
                    <p>{formatLastReadingDate(meter.dt_last_indication)}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
