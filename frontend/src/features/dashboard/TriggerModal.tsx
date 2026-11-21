import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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

  if (!open) return null;

  const filtered = (flights || []).filter(
    (f) =>
      f.flight_number.toLowerCase().includes(search.toLowerCase()) ||
      f.origin.toLowerCase().includes(search.toLowerCase()) ||
      f.destination.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold text-gray-900">Trigger Flight Cancellation</h2>
        <p className="mt-1 text-sm text-gray-500">Select a flight to cancel and start the recovery pipeline</p>

        <input
          type="text"
          placeholder="Search flights..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="mt-4 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-red-500 focus:outline-none"
        />

        <div className="mt-3 max-h-48 overflow-y-auto space-y-1">
          {filtered.slice(0, 20).map((f) => (
            <button
              key={f.flight_number}
              onClick={() => setSelected(f)}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                selected?.flight_number === f.flight_number
                  ? 'bg-red-50 border border-red-400 font-medium'
                  : 'hover:bg-gray-50 border border-transparent'
              }`}
            >
              <span className="font-medium">{f.flight_number}</span>
              <span className="ml-2 text-gray-500">{f.origin} &rarr; {f.destination}</span>
              <span className="ml-2 text-gray-400">{f.dep_time}</span>
            </button>
          ))}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-600">Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600">Reason</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="technical">Technical</option>
              <option value="weather">Weather</option>
              <option value="crew">Crew</option>
              <option value="operational">Operational</option>
            </select>
          </div>
        </div>

        <div className="mt-5 flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!selected || mutation.isPending}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Processing...' : 'Cancel Flight'}
          </button>
        </div>

        {mutation.isError && (
          <p className="mt-2 text-sm text-red-600">{(mutation.error as Error).message}</p>
        )}
      </div>
    </div>
  );
}
