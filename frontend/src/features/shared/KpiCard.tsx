import { Card, CardContent } from '@/components/ui/card';

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}

export function KpiCard({ label, value, sub, color = 'text-foreground' }: Props) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p className={`mt-1 text-3xl font-bold ${color}`}>{value}</p>
        {sub && <p className="mt-1 text-xs text-muted-foreground/70">{sub}</p>}
      </CardContent>
    </Card>
  );
}
