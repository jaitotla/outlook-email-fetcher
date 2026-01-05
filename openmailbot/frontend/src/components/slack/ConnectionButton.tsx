'use client'

import { Slack } from 'lucide-react';

interface ConnectionButtonProps {
  onConnect: () => void;
  className?: string;
}

export default function ConnectionButton({ onConnect, className = '' }: ConnectionButtonProps) {
  return (
    <button
      onClick={onConnect}
      className={`flex items-center gap-2 bg-[#4A154B] hover:bg-[#611f69] text-white px-6 py-3 rounded-lg font-medium transition-colors ${className}`}
    >
      <Slack className="w-5 h-5" />
      Connect to Slack
    </button>
  );
}
