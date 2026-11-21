import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { dashboardApi } from '../../api/dashboard';
import { disruptionApi, type Disruption } from '../../api/disruptions';
import { notificationApi } from '../../api/notifications';
import { useWebSocket } from '../../hooks/useWebSocket';
import { KpiCard } from '../shared/KpiCard';
import { StatusBadge } from '../shared/StatusBadge';
import { PassengerTable } from './PassengerTable';
import { TriggerModal } from './TriggerModal';

export function DashboardPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { lastEvent, connected } = useWebSocket();

  useEffect(() => {
    if (lastEvent) {
      queryClient.invalidateQueries({ queryKey: ['disruptions'] });
      queryClient.invalidateQueries({ queryKey: ['kpis'] });
      if (selectedId) {
        queryClient.invalidateQueries({ queryKey: ['passengers', selectedId] });
      }
    }
  }, [lastEvent, queryClient, selectedId]);

  const { data: disruptions } = useQuery({
    queryKey: ['disruptions'],
    queryFn: disruptionApi.list,
  });

  const { data: kpis } = useQuery({
    queryKey: ['kpis', selectedId],
    queryFn: () => dashboardApi.kpis(selectedId ?? undefined),
  });

  const { data: passengers } = useQuery({
    queryKey: ['passengers', selectedId],
    queryFn: () => disruptionApi.passengers(selectedId!),
    enabled: !!selectedId,
  });

  const notify = useMutation({
    mutationFn: (id: number) => notificationApi.send(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['passengers', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['kpis'] });
    },
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600">
              <span className="text-sm font-bold text-white">G9</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">OCC Recovery Dashboard</h1>
              <p className="text-xs text-gray-500">Air Arabia Disruption Management</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-green-600' : 'text-red-500'}`}>
              <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
              {connected ? 'Live' : 'Disconnected'}
            </span>
            <button
              onClick={() => setModalOpen(true)}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Trigger Cancellation
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {kpis && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <KpiCard label="Affected PAX" value={kpis.affected_pax_count} color="text-red-600" />
            <KpiCard label="Recovered" value={kpis.recovered_pax_count} color="text-green-600"
              sub={`${kpis.self_service_rate}% self-service`} />
            <KpiCard label="Self-Served" value={kpis.self_service_count} color="text-blue-600" />
            <KpiCard label="Pending" value={kpis.pending_count + kpis.notified_count}
              sub={`${kpis.notified_count} notified`} />
            <KpiCard label="Recovery Cost" value={`$${kpis.total_recovery_cost.toLocaleString()}`}
              sub={kpis.avg_recovery_time_seconds
                ? `Avg ${Math.round(kpis.avg_recovery_time_seconds / 60)}m recovery`
                : undefined} />
          </div>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-4">
          <div className="lg:col-span-1">
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <h2 className="text-sm font-semibold text-gray-900">Disruption Events</h2>
              <div className="mt-3 space-y-2">
                {(disruptions || []).map((d: Disruption) => (
                  <button
                    key={d.id}
                    onClick={() => setSelectedId(d.id)}
                    className={`w-full rounded-lg border p-3 text-left text-sm transition-colors ${
                      selectedId === d.id
                        ? 'border-red-400 bg-red-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{d.flight_number}</span>
                      <StatusBadge status={d.disruption_type} />
                    </div>
                    <p className="mt-1 text-xs text-gray-500">{d.flight_date} &middot; {d.reason}</p>
                    <p className="mt-1 text-xs text-gray-400">
                      {d.affected_pax_count} PAX &middot; {d.recovered_pax_count} recovered
                    </p>
                  </button>
                ))}
                {(!disruptions || disruptions.length === 0) && (
                  <p className="py-4 text-center text-xs text-gray-400">
                    No disruptions yet. Trigger one to start.
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="rounded-xl border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">
                  Affected Passengers {selectedId ? `(Event #${selectedId})` : ''}
                </h2>
                {selectedId && (
                  <button
                    onClick={() => notify.mutate(selectedId)}
                    disabled={notify.isPending}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {notify.isPending ? 'Sending...' : 'Send Notifications'}
                  </button>
                )}
              </div>
              <div className="mt-4">
                {selectedId && passengers ? (
                  <PassengerTable passengers={passengers} />
                ) : (
                  <p className="py-12 text-center text-sm text-gray-400">
                    Select a disruption event to view affected passengers
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <TriggerModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
