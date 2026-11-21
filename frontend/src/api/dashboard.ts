import { api } from './client';

export interface CostBreakdown {
  hotel: number;
  meal: number;
  compensation: number;
  rebooking: number;
  refund: number;
  total: number;
}

export interface Kpis {
  affected_pax_count: number;
  recovered_pax_count: number;
  self_service_count: number;
  refund_count: number;
  self_service_rate: number;
  avg_recovery_time_seconds: number | null;
  total_recovery_cost: number;
  cost_breakdown: CostBreakdown | null;
  pending_count: number;
  notified_count: number;
}

export interface FlightInfo {
  flight_number: string;
  origin: string;
  destination: string;
  dep_time: string;
  arr_time: string;
}

export const dashboardApi = {
  kpis: (disruptionId?: number) =>
    api.get<Kpis>(`/dashboard/kpis${disruptionId ? `?disruption_id=${disruptionId}` : ''}`),
  flights: () => api.get<FlightInfo[]>('/dashboard/flights'),
};
