import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { dashboardApi, type FlightInfo } from '../../api/dashboard';
import { disruptionApi } from '../../api/disruptions';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function TriggerModal({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<FlightInfo | null>(null);
  const [date, setDate] = useState('2027-03-04');
  const [reason, setReason] = useState('technical');
  const [search, setSearch] = useState('');

  const { data: flights } = useQuery({
    queryKey: ['flights'],
    queryFn: dashboardApi.flights,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () =>
      disruptionApi.create({
        flight_number: selected!.flight_number,
        flight_date: date,
        disruption_type: 'cancellation',
        reason,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['disruptions'] });
      queryClient.invalidateQueries({ queryKey: ['kpis'] });
      onClose();
    },
  });

  const filtered = (flights || []).filter(
    (f) =>
      f.flight_number.toLowerCase().includes(search.toLowerCase()) ||
      f.origin.toLowerCase().includes(search.toLowerCase()) ||
      f.destination.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Trigger Flight Cancellation</DialogTitle>
          <DialogDescription>Select a flight to cancel and start the recovery pipeline</DialogDescription>
        </DialogHeader>

        <Input
          placeholder="Search flights..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div className="max-h-48 overflow-y-auto space-y-1">
          {filtered.slice(0, 20).map((f) => (
            <button
              key={f.flight_number}
              onClick={() => setSelected(f)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                selected?.flight_number === f.flight_number
                  ? 'bg-destructive/10 border border-destructive font-medium'
                  : 'hover:bg-muted border border-transparent'
              }`}
            >
              <span className="font-medium">{f.flight_number}</span>
              <span className="ml-2 text-muted-foreground">{f.origin} &rarr; {f.destination}</span>
              <span className="ml-2 text-muted-foreground/70">{f.dep_time}</span>
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Date</label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Reason</label>
            <Select value={reason} onValueChange={(v) => v && setReason(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="technical">Technical</SelectItem>
                <SelectItem value="weather">Weather</SelectItem>
                <SelectItem value="crew">Crew</SelectItem>
                <SelectItem value="operational">Operational</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={() => mutation.mutate()}
            disabled={!selected || mutation.isPending}
          >
            {mutation.isPending ? 'Processing...' : 'Cancel Flight'}
          </Button>
        </DialogFooter>

        {mutation.isError && (
          <p className="text-sm text-destructive">{(mutation.error as Error).message}</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
