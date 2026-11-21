import { api } from './client';

export interface Disruption {
  id: number;
  flight_number: string;
  flight_date: string;
  disruption_type: string;
  reason: string | null;
  created_at: string | null;
  status: string;
  affected_pax_count: number;
  recovered_pax_count: number;
}

export interface CreateDisruptionRequest {
  flight_number: string;
  flight_date: string;
  disruption_type?: string;
  reason?: string;
}

export interface Passenger {
  id: number;
  disruption_id: number;
  pnr: string;
  passenger_name: string | null;
  pax_type: string | null;
  is_connecting: boolean;
  is_misconnect: boolean;
  connecting_flight: string | null;
  priority_score: number;
  loyalty_tier: string | null;
  total_fare: number;
  original_segment: string | null;
  recovery_status: string;
  recovery_flight: string | null;
  notified_at: string | null;
  recovered_at: string | null;
  email: string | null;
  phone: string | null;
}

export const disruptionApi = {
  list: () => api.get<Disruption[]>('/disruptions'),
  get: (id: number) => api.get<Disruption>(`/disruptions/${id}`),
  create: (data: CreateDisruptionRequest) =>
    api.post<Disruption>('/disruptions', data),
  passengers: (id: number) => api.get<Passenger[]>(`/disruptions/${id}/passengers`),
};
