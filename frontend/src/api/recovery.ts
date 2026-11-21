import { api } from './client';

export interface RecoveryOption {
  id: number;
  flight_number: string;
  origin: string | null;
  destination: string | null;
  departure_time: string | null;
  arrival_time: string | null;
  available_seats: number;
  fare_difference: number;
  rank: number;
  status: string;
}

export interface RecoveryInfo {
  disruption_type: string;
  flight_number: string;
  flight_date: string;
  passenger_name: string | null;
  pnr: string;
  original_segment: string | null;
  recovery_status: string;
  options: RecoveryOption[];
}

export const recoveryApi = {
  getInfo: (token: string) => api.get<RecoveryInfo>(`/recovery/${token}`),
  accept: (token: string, optionId: number) =>
    api.post(`/recovery/${token}/accept`, { option_id: optionId, action: 'accept' }),
  refund: (token: string) =>
    api.post(`/recovery/${token}/accept`, { action: 'refund' }),
};
