import type { Passenger } from '../../api/disruptions';
import { StatusBadge } from '../shared/StatusBadge';

interface Props {
  passengers: Passenger[];
}

export function PassengerTable({ passengers }: Props) {
  if (passengers.length === 0) {
    return <p className="py-8 text-center text-sm text-gray-400">No affected passengers</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-xs font-medium uppercase text-gray-500">
            <th className="pb-3 pr-4">Priority</th>
            <th className="pb-3 pr-4">PNR</th>
            <th className="pb-3 pr-4">Passenger</th>
            <th className="pb-3 pr-4">Type</th>
            <th className="pb-3 pr-4">Segment</th>
            <th className="pb-3 pr-4">Connecting</th>
            <th className="pb-3 pr-4">Loyalty</th>
            <th className="pb-3 pr-4">Status</th>
            <th className="pb-3">Recovery</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {passengers.map((p) => (
            <tr key={p.id} className="hover:bg-gray-50">
              <td className="py-3 pr-4">
                <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                  p.priority_score >= 10 ? 'bg-red-100 text-red-700' :
                  p.priority_score >= 5 ? 'bg-orange-100 text-orange-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {p.priority_score}
                </span>
              </td>
              <td className="py-3 pr-4 font-mono text-xs">{p.pnr}</td>
              <td className="py-3 pr-4 font-medium text-gray-900">{p.passenger_name}</td>
              <td className="py-3 pr-4 text-gray-500">{p.pax_type}</td>
              <td className="py-3 pr-4 text-gray-500">{p.original_segment}</td>
              <td className="py-3 pr-4">
                {p.is_misconnect ? (
                  <span className="text-red-600 font-medium">Misconnect</span>
                ) : p.is_connecting ? (
                  <span className="text-orange-600">Connecting</span>
                ) : (
                  <span className="text-gray-400">Direct</span>
                )}
              </td>
              <td className="py-3 pr-4">
                {p.loyalty_tier ? (
                  <span className={`font-medium ${
                    p.loyalty_tier === 'Gold' ? 'text-yellow-600' :
                    p.loyalty_tier === 'Silver' ? 'text-gray-500' : 'text-gray-400'
                  }`}>{p.loyalty_tier}</span>
                ) : <span className="text-gray-300">-</span>}
              </td>
              <td className="py-3 pr-4"><StatusBadge status={p.recovery_status} /></td>
              <td className="py-3 text-gray-500">{p.recovery_flight || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
