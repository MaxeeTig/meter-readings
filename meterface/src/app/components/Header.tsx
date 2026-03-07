import { Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  online?: boolean;
}

export function Header({ online = true }: HeaderProps) {
  return (
    <header className="bg-card border-b border-border">
      <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl text-foreground">Meter Readings</h1>
            <p className="mt-1 text-sm text-muted-foreground">Upload photo, verify, save</p>
          </div>
          <div
            className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
              online
                ? 'bg-success/10 text-success'
                : 'bg-destructive/10 text-destructive'
            }`}
          >
            {online ? (
              <>
                <Wifi className="w-4 h-4" />
                <span>Online</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4" />
                <span>Offline</span>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
