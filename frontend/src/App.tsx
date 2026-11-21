import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { RecoveryPage } from './features/recovery/RecoveryPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/recover/:token" element={<RecoveryPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
