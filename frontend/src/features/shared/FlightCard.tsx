interface Props {
  flightNumber: string;
  origin: string;
  destination: string;
  depTime: string;
  arrTime?: string;
  selected?: boolean;
  onClick?: () => void;
}

export function FlightCard({ flightNumber, origin, destination, depTime, arrTime, selected, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-lg border p-3 text-left transition-colors ${
        selected
          ? 'border-red-500 bg-red-50'
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-gray-900">{flightNumber}</span>
        <span className="text-sm text-gray-500">{depTime}{arrTime ? ` - ${arrTime}` : ''}</span>
      </div>
      <p className="mt-1 text-sm text-gray-600">
        {origin} &rarr; {destination}
      </p>
    </button>
  );
}
