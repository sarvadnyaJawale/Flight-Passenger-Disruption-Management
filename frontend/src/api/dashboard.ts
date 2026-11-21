import { api } from './client';

export interface CostBreakdown {
  hotel: number;
  meal: number;
  compensation: number;
  rebooking: number;
  refund: number;
  total: number;
}

export interface DoNothingBaseline {
  stranded_pax: number;
  eu261_compensation: number;
  hotel_cost: number;
  meal_cost: number;
  total_liability: number;
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
  do_nothing_baseline: DoNothingBaseline | null;
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

export interface StrategyAlternative {
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
  arrival_time: string;
  available_seats: number;
  fare_difference: number;
}

export interface RecoveryStrategies {
  cheapest: StrategyAlternative[];
  fastest: StrategyAlternative[];
  best_experience: StrategyAlternative[];
}

export const dashboardApi = {
  kpis: (disruptionId?: number) =>
    api.get<Kpis>(`/dashboard/kpis${disruptionId ? `?disruption_id=${disruptionId}` : ''}`),
  flights: () => api.get<FlightInfo[]>('/dashboard/flights'),
  strategies: (disruptionId: number) =>
    api.get<RecoveryStrategies>(`/costs/${disruptionId}/strategies`),
};
