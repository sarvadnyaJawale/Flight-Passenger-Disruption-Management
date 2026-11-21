import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { recoveryApi, type RecoveryOption } from '../../api/recovery';
import { StatusBadge } from '../shared/StatusBadge';

export function RecoveryPage() {
  const { token } = useParams<{ token: string }>();
  const queryClient = useQueryClient();

  const { data: info, isLoading, error } = useQuery({
    queryKey: ['recovery', token],
    queryFn: () => recoveryApi.getInfo(token!),
    enabled: !!token,
  });

  const accept = useMutation({
    mutationFn: (optionId: number) => recoveryApi.accept(token!, optionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recovery', token] }),
  });

  const refund = useMutation({
    mutationFn: () => recoveryApi.refund(token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['recovery', token] }),
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="animate-pulse text-muted-foreground">Loading your recovery options...</p>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Card className="max-w-sm text-center">
          <CardContent className="p-8">
            <p className="text-lg font-semibold text-destructive">Link Expired or Invalid</p>
            <p className="mt-2 text-sm text-muted-foreground">Please contact Air Arabia support for assistance.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isResolved = ['self_served', 'refunded', 'manually_handled'].includes(info.recovery_status);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto max-w-2xl px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-destructive">
              <span className="text-sm font-bold text-destructive-foreground">G9</span>
            </div>
            <div>
              <h1 className="text-lg font-bold">Air Arabia Recovery Portal</h1>
              <p className="text-xs text-muted-foreground">Self-Service Re-accommodation</p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-destructive">Flight {info.disruption_type}</p>
                <p className="mt-1 text-2xl font-bold">{info.flight_number}</p>
              </div>
              <StatusBadge status={info.recovery_status} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Date</p>
                <p className="font-medium">{info.flight_date}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Route</p>
                <p className="font-medium">{info.original_segment?.replace('/', ' → ')}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Passenger</p>
                <p className="font-medium">{info.passenger_name}</p>
              </div>
              <div>
                <p className="text-muted-foreground">PNR</p>
                <p className="font-mono font-medium">{info.pnr}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {isResolved ? (
          <Card className="mt-6 border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950">
            <CardContent className="p-6 text-center">
              <p className="text-lg font-semibold text-green-800 dark:text-green-200">
                {info.recovery_status === 'refunded' ? 'Refund Requested' : 'Rebooked Successfully'}
              </p>
              <p className="mt-2 text-sm text-green-600 dark:text-green-400">
                {info.recovery_status === 'refunded'
                  ? 'Your refund will be processed within 7-14 business days.'
                  : 'Your new booking has been confirmed. Check your email for details.'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            <h2 className="mt-8 text-lg font-semibold">Available Alternatives</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Select one of the following alternative flights, or request a full refund.
            </p>

            <div className="mt-4 space-y-3">
              {info.options.map((opt: RecoveryOption) => (
                <Card key={opt.id}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-lg font-semibold">{opt.flight_number}</p>
                        <p className="text-sm text-muted-foreground">
                          {opt.origin} &rarr; {opt.destination}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">
                          {opt.departure_time} - {opt.arrival_time}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {opt.available_seats} seats available
                        </p>
                      </div>
                    </div>
                    {opt.fare_difference !== 0 && (
                      <p className="mt-2 text-sm text-orange-600">
                        Fare difference: AED {Math.abs(opt.fare_difference).toFixed(2)}
                        {opt.fare_difference > 0 ? ' surcharge' : ' credit'}
                      </p>
                    )}
                    <Button
                      className="mt-3 w-full"
                      onClick={() => accept.mutate(opt.id)}
                      disabled={accept.isPending}
                    >
                      {accept.isPending ? 'Processing...' : `Select ${opt.flight_number}`}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="mt-6 border-t pt-6">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => refund.mutate()}
                disabled={refund.isPending}
              >
                {refund.isPending ? 'Processing...' : 'Request Full Refund Instead'}
              </Button>
            </div>
          </>
        )}

        {(accept.isError || refund.isError) && (
          <p className="mt-4 text-center text-sm text-destructive">
            Something went wrong. Please try again.
          </p>
        )}
      </main>
    </div>
  );
}
