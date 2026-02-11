import { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import { Activity } from 'lucide-react';

export function ConnectionStatus() {
  const [status, setStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  useEffect(() => {
    const checkConnection = async () => {
      setStatus('checking');
      try {
        await api.healthCheck();
        setStatus('connected');
        setLastCheck(new Date());
      } catch {
        setStatus('disconnected');
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const getBadgeVariant = () => {
    switch (status) {
      case 'connected':
        return 'default';
      case 'disconnected':
        return 'destructive';
      case 'checking':
        return 'secondary';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'connected':
        return 'Connected';
      case 'disconnected':
        return 'Disconnected';
      case 'checking':
        return 'Checking...';
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg">
      <Activity className="w-4 h-4 text-muted-foreground" />
      <span className="text-sm text-muted-foreground">Backend:</span>
      <Badge variant={getBadgeVariant()} className="text-xs">
        {getStatusText()}
      </Badge>
      {lastCheck && status === 'connected' && (
        <span className="text-xs text-muted-foreground ml-2">
          Last check: {lastCheck.toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}

export default ConnectionStatus;
