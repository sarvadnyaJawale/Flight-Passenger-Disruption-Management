import { Badge } from '@/components/ui/badge';

const STATUS_VARIANTS: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'outline',
  notified: 'secondary',
  options_viewed: 'secondary',
  self_served: 'default',
  manually_handled: 'default',
  refunded: 'secondary',
  active: 'destructive',
  cancellation: 'destructive',
  delay: 'outline',
};

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANTS[status] || 'outline';
  return (
    <Badge variant={variant}>
      {status.replace(/_/g, ' ')}
    </Badge>
  );
}
