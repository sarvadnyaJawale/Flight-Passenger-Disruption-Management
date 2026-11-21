import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import type { Passenger } from '../../api/disruptions';
import { StatusBadge } from '../shared/StatusBadge';

interface Props {
  passengers: Passenger[];
}

export function PassengerTable({ passengers }: Props) {
  if (passengers.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No affected passengers</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">Priority</TableHead>
          <TableHead>PNR</TableHead>
          <TableHead>Passenger</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Segment</TableHead>
          <TableHead>Connecting</TableHead>
          <TableHead>Loyalty</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Recovery</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {passengers.map((p) => (
          <TableRow key={p.id}>
            <TableCell>
              <Badge variant={p.priority_score >= 10 ? 'destructive' : p.priority_score >= 5 ? 'default' : 'secondary'}>
                {p.priority_score}
              </Badge>
            </TableCell>
            <TableCell className="font-mono text-xs">{p.pnr}</TableCell>
            <TableCell className="font-medium">{p.passenger_name}</TableCell>
            <TableCell className="text-muted-foreground">{p.pax_type}</TableCell>
            <TableCell className="text-muted-foreground">{p.original_segment}</TableCell>
            <TableCell>
              {p.is_misconnect ? (
                <Badge variant="destructive">Misconnect</Badge>
              ) : p.is_connecting ? (
                <Badge variant="outline">Connecting</Badge>
              ) : (
                <span className="text-muted-foreground">Direct</span>
              )}
            </TableCell>
            <TableCell>
              {p.loyalty_tier ? (
                <Badge variant={p.loyalty_tier === 'Gold' ? 'default' : 'secondary'}>
                  {p.loyalty_tier}
                </Badge>
              ) : <span className="text-muted-foreground">-</span>}
            </TableCell>
            <TableCell><StatusBadge status={p.recovery_status} /></TableCell>
            <TableCell className="text-muted-foreground">{p.recovery_flight || '-'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
