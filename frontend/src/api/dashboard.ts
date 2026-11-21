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

export interface DownstreamFlight {
  flight_number: string;
  origin: string;
  destination: string;
  departure_time: string;
}

export interface CascadeImpact {
  cancelled_flight: string | null;
  route: string | null;
  downstream_flights: DownstreamFlight[];
}

export interface FlightRisk {
  flight_number: string;
  route: string;
  risk_score: number;
  risk_level: string;
  factors: {
    load_factor: number;
    departure_hour: number;
    route_alternatives: number;
    connecting_hub: boolean;
  };
}

export interface WhatIfResult {
  affected_pax: number;
  delay_minutes: number;
  total_do_nothing_cost: number;
  total_recovery_cost: number;
  net_savings: number;
  savings_pct: number;
}

export interface AiAnalysis {
  answer: string;
  provider: string;
  question: string;
}

export const dashboardApi = {
  kpis: (disruptionId?: number) =>
    api.get<Kpis>(`/dashboard/kpis${disruptionId ? `?disruption_id=${disruptionId}` : ''}`),
  flights: () => api.get<FlightInfo[]>('/dashboard/flights'),
  strategies: (disruptionId: number) =>
    api.get<RecoveryStrategies>(`/costs/${disruptionId}/strategies`),
  cascade: (disruptionId: number) =>
    api.get<CascadeImpact>(`/costs/${disruptionId}/cascade`),
  flightRisk: (flightNumber: string) =>
    api.get<FlightRisk>(`/costs/risk/${flightNumber}`),
  simulate: (params: { affected_pax: number; delay_minutes: number; hotel_nights: number; include_compensation: boolean }) =>
    api.post<WhatIfResult>(`/costs/simulate?affected_pax=${params.affected_pax}&delay_minutes=${params.delay_minutes}&hotel_nights=${params.hotel_nights}&include_compensation=${params.include_compensation}`, {}),
  aiAnalyze: (disruptionId: number) =>
    api.post<AiAnalysis>(`/costs/ai/analyze?disruption_id=${disruptionId}`, {}),
};
