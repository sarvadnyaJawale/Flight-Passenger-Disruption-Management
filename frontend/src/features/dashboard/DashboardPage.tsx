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

  const { data: strategies } = useQuery({
    queryKey: ['strategies', selectedId],
    queryFn: () => dashboardApi.strategies(selectedId!),
    enabled: !!selectedId,
  });

  const { data: cascade } = useQuery({
    queryKey: ['cascade', selectedId],
    queryFn: () => dashboardApi.cascade(selectedId!),
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
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              <KpiCard label="Affected PAX" value={kpis.affected_pax_count} color="text-destructive" />
              <KpiCard label="Recovered" value={kpis.recovered_pax_count} color="text-green-600"
                sub={`${kpis.self_service_rate}% self-service`} />
              <KpiCard label="Self-Served" value={kpis.self_service_count} color="text-blue-600" />
              <KpiCard label="Pending" value={kpis.pending_count + kpis.notified_count}
                sub={`${kpis.notified_count} notified`} />
              <KpiCard label="Total Cost" value={`AED ${kpis.total_recovery_cost.toLocaleString()}`}
                sub={kpis.avg_recovery_time_seconds
                  ? `Avg ${Math.round(kpis.avg_recovery_time_seconds / 60)}m recovery`
                  : undefined} />
            </div>
            {kpis.cost_breakdown && (
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                <KpiCard label="Hotel" value={`AED ${kpis.cost_breakdown.hotel.toLocaleString()}`} color="text-orange-600" />
                <KpiCard label="Meals" value={`AED ${kpis.cost_breakdown.meal.toLocaleString()}`} color="text-amber-600" />
                <KpiCard label="Compensation" value={`AED ${kpis.cost_breakdown.compensation.toLocaleString()}`} color="text-purple-600" />
                <KpiCard label="Rebooking" value={`AED ${kpis.cost_breakdown.rebooking.toLocaleString()}`} color="text-sky-600" />
                <KpiCard label="Refunds" value={`AED ${kpis.cost_breakdown.refund.toLocaleString()}`} color="text-rose-600" />
              </div>
            )}
            {kpis.do_nothing_baseline && kpis.cost_breakdown && (
              <div className="mt-4 rounded-lg border border-dashed border-destructive/30 bg-destructive/5 p-4">
                <h3 className="mb-3 text-sm font-semibold text-destructive">If No Action Taken</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  <KpiCard label="Stranded PAX" value={kpis.do_nothing_baseline.stranded_pax} color="text-destructive" />
                  <KpiCard label="EU261 Liability" value={`AED ${kpis.do_nothing_baseline.eu261_compensation.toLocaleString()}`} color="text-destructive" />
                  <KpiCard label="Total Liability" value={`AED ${kpis.do_nothing_baseline.total_liability.toLocaleString()}`} color="text-destructive" />
                  <KpiCard label="Recovery Saved"
                    value={`AED ${(kpis.do_nothing_baseline.total_liability - kpis.cost_breakdown.total).toLocaleString()}`}
                    color="text-green-600" />
                  <KpiCard label="Cost Reduction"
                    value={`${Math.round(((kpis.do_nothing_baseline.total_liability - kpis.cost_breakdown.total) / kpis.do_nothing_baseline.total_liability) * 100)}%`}
                    color="text-green-600" />
                </div>
              </div>
            )}
            {strategies && strategies.cheapest.length > 0 && (
              <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
                {([
                  { key: 'cheapest' as const, label: 'Lowest Cost', color: 'text-green-600', border: 'border-green-200' },
                  { key: 'fastest' as const, label: 'Earliest Departure', color: 'text-blue-600', border: 'border-blue-200' },
                  { key: 'best_experience' as const, label: 'Best Experience', color: 'text-purple-600', border: 'border-purple-200' },
                ]).map(({ key, label, color, border }) => (
                  <Card key={key} className={`border ${border}`}>
                    <CardContent className="p-4">
                      <h4 className={`mb-2 text-sm font-semibold ${color}`}>{label}</h4>
                      <div className="space-y-2">
                        {strategies[key].slice(0, 3).map((alt, i) => (
                          <div key={alt.flight_number} className="flex items-center justify-between text-sm">
                            <span className="font-mono">{i + 1}. {alt.flight_number}</span>
                            <span className="text-muted-foreground">{alt.departure_time} · {alt.available_seats} seats · AED {alt.fare_difference}</span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
            {cascade && cascade.downstream_flights.length > 0 && (
              <Card className="mt-4 border-amber-200 bg-amber-50/50 dark:bg-amber-950/20">
                <CardContent className="p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="text-lg">⚠️</span>
                    <h4 className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                      Cascade Impact — {cascade.downstream_flights.length} downstream flight{cascade.downstream_flights.length > 1 ? 's' : ''} at risk
                    </h4>
                  </div>
                  <p className="mb-3 text-xs text-muted-foreground">
                    Flight {cascade.cancelled_flight} ({cascade.route}) cancellation may disrupt aircraft rotation for these departures:
                  </p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {cascade.downstream_flights.map((f) => (
                      <div key={f.flight_number} className="flex items-center justify-between rounded-md border border-amber-200 bg-white/80 px-3 py-2 text-sm dark:bg-amber-950/30">
                        <span className="font-mono font-semibold">{f.flight_number}</span>
                        <span className="text-muted-foreground">{f.origin} → {f.destination}</span>
                        <span className="text-xs text-amber-600">{f.departure_time}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
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
