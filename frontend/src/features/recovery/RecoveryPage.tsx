import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
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
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="animate-pulse text-gray-400">Loading your recovery options...</div>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="rounded-xl bg-white p-8 text-center shadow-lg">
          <p className="text-lg font-semibold text-red-600">Link Expired or Invalid</p>
          <p className="mt-2 text-sm text-gray-500">Please contact Air Arabia support for assistance.</p>
        </div>
      </div>
    );
  }

  const isResolved = ['self_served', 'refunded', 'manually_handled'].includes(info.recovery_status);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600">
              <span className="text-sm font-bold text-white">G9</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">Air Arabia Recovery Portal</h1>
              <p className="text-xs text-gray-500">Self-Service Re-accommodation</p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-red-800">Flight {info.disruption_type}</p>
              <p className="mt-1 text-2xl font-bold text-red-900">{info.flight_number}</p>
            </div>
            <StatusBadge status={info.recovery_status} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-red-600">Date</p>
              <p className="font-medium text-red-900">{info.flight_date}</p>
            </div>
            <div>
              <p className="text-red-600">Route</p>
              <p className="font-medium text-red-900">{info.original_segment?.replace('/', ' → ')}</p>
            </div>
            <div>
              <p className="text-red-600">Passenger</p>
              <p className="font-medium text-red-900">{info.passenger_name}</p>
            </div>
            <div>
              <p className="text-red-600">PNR</p>
              <p className="font-mono font-medium text-red-900">{info.pnr}</p>
            </div>
          </div>
        </div>

        {isResolved ? (
          <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-6 text-center">
            <p className="text-lg font-semibold text-green-800">
              {info.recovery_status === 'refunded' ? 'Refund Requested' : 'Rebooked Successfully'}
            </p>
            <p className="mt-2 text-sm text-green-600">
              {info.recovery_status === 'refunded'
                ? 'Your refund will be processed within 7-14 business days.'
                : 'Your new booking has been confirmed. Check your email for details.'}
            </p>
          </div>
        ) : (
          <>
            <h2 className="mt-8 text-lg font-semibold text-gray-900">Available Alternatives</h2>
            <p className="mt-1 text-sm text-gray-500">
              Select one of the following alternative flights, or request a full refund.
            </p>

            <div className="mt-4 space-y-3">
              {info.options.map((opt: RecoveryOption) => (
                <div
                  key={opt.id}
                  className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-semibold text-gray-900">{opt.flight_number}</p>
                      <p className="text-sm text-gray-500">
                        {opt.origin} &rarr; {opt.destination}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-gray-900">
                        {opt.departure_time} - {opt.arrival_time}
                      </p>
                      <p className="text-xs text-gray-400">
                        {opt.available_seats} seats available
                      </p>
                    </div>
                  </div>
                  {opt.fare_difference !== 0 && (
                    <p className="mt-2 text-sm text-orange-600">
                      Fare difference: ${Math.abs(opt.fare_difference)}
                      {opt.fare_difference > 0 ? ' surcharge' : ' refund'}
                    </p>
                  )}
                  <button
                    onClick={() => accept.mutate(opt.id)}
                    disabled={accept.isPending}
                    className="mt-3 w-full rounded-lg bg-green-600 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    {accept.isPending ? 'Processing...' : `Select ${opt.flight_number}`}
                  </button>
                </div>
              ))}
            </div>

            <div className="mt-6 border-t border-gray-200 pt-6">
              <button
                onClick={() => refund.mutate()}
                disabled={refund.isPending}
                className="w-full rounded-lg border border-gray-300 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {refund.isPending ? 'Processing...' : 'Request Full Refund Instead'}
              </button>
            </div>
          </>
        )}

        {(accept.isError || refund.isError) && (
          <p className="mt-4 text-center text-sm text-red-600">
            Something went wrong. Please try again.
          </p>
        )}
      </main>
    </div>
  );
}
