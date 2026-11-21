const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  notified: 'bg-blue-100 text-blue-800',
  options_viewed: 'bg-indigo-100 text-indigo-800',
  self_served: 'bg-green-100 text-green-800',
  manually_handled: 'bg-teal-100 text-teal-800',
  refunded: 'bg-purple-100 text-purple-800',
  active: 'bg-red-100 text-red-800',
  cancellation: 'bg-red-100 text-red-800',
  delay: 'bg-orange-100 text-orange-800',
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || 'bg-gray-100 text-gray-800';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}
