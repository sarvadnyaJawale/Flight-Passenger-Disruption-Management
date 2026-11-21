import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { dashboardApi } from '../../api/dashboard';
import { disruptionApi, type Disruption } from '../../api/disruptions';
import { notificationApi } from '../../api/notifications';
import { useWebSocket } from '../../hooks/useWebSocket';
import { KpiCard } from '../shared/KpiCard';
import { NotificationInbox } from '../shared/NotificationInbox';
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
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-destructive">
              <span className="text-sm font-bold text-destructive-foreground">G9</span>
            </div>
            <div>
              <h1 className="text-lg font-bold">OCC Recovery Dashboard</h1>
              <p className="text-xs text-muted-foreground">Air Arabia Disruption Management</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <NotificationInbox />
            <Badge variant={connected ? 'default' : 'destructive'}>
              {connected ? 'Live' : 'Disconnected'}
            </Badge>
            <Button variant="destructive" onClick={() => setModalOpen(true)}>
              Trigger Cancellation
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {kpis && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <KpiCard label="Affected PAX" value={kpis.affected_pax_count} color="text-destructive" />
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
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Disruption Events</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {(disruptions || []).map((d: Disruption) => (
                  <button
                    key={d.id}
                    onClick={() => setSelectedId(d.id)}
                    className={`w-full rounded-md border p-3 text-left text-sm transition-colors ${
                      selectedId === d.id
                        ? 'border-destructive bg-destructive/5'
                        : 'border-border hover:border-primary/30'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{d.flight_number}</span>
                      <StatusBadge status={d.disruption_type} />
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{d.flight_date} &middot; {d.reason}</p>
                    <p className="mt-1 text-xs text-muted-foreground/70">
                      {d.affected_pax_count} PAX &middot; {d.recovered_pax_count} recovered
                    </p>
                  </button>
                ))}
                {(!disruptions || disruptions.length === 0) && (
                  <p className="py-4 text-center text-xs text-muted-foreground">
                    No disruptions yet. Trigger one to start.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <CardTitle className="text-sm">
                  Affected Passengers {selectedId ? `(Event #${selectedId})` : ''}
                </CardTitle>
                {selectedId && (
                  <Button
                    size="sm"
                    onClick={() => notify.mutate(selectedId)}
                    disabled={notify.isPending}
                  >
                    {notify.isPending ? 'Sending...' : 'Send Notifications'}
                  </Button>
                )}
              </CardHeader>
              <CardContent>
                {selectedId && passengers ? (
                  <PassengerTable passengers={passengers} />
                ) : (
                  <p className="py-12 text-center text-sm text-muted-foreground">
                    Select a disruption event to view affected passengers
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      <TriggerModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
