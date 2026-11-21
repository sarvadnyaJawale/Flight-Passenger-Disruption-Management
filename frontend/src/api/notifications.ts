import { api } from './client';

export interface NotificationResult {
  disruption_id: number;
  sent_count: number;
  deep_links: Array<{
    pnr: string;
    name: string;
    email: string;
    deep_link: string;
  }>;
}

export const notificationApi = {
  send: (disruptionId: number) =>
    api.post<NotificationResult>(`/notifications/${disruptionId}/send`, {}),
};
