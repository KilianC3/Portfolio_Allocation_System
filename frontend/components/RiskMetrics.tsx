import React, { useEffect, useState } from 'react';
import { MetricsSocket } from '../utils/socket';

interface MetricPoint {
  date: string;
  var: number;
  cvar: number;
  drawdown: number;
}

/**
 * Component displaying VaR, CVaR and drawdown metrics in real time.
 */
export const RiskMetrics: React.FC<{ pfId: string }> = ({ pfId }) => {
  const [points, setPoints] = useState<MetricPoint[]>([]);

  useEffect(() => {
    const handler = (msg: any) => {
      if (msg.type === 'metrics' && msg.portfolio_id === pfId) {
        setPoints((prev) => [
          ...prev,
          {
            date: msg.date,
            var: msg.metrics.var,
            cvar: msg.metrics.cvar,
            drawdown: msg.metrics.max_drawdown,
          },
        ]);
      }
    };
    const socket = new MetricsSocket('/ws/metrics', handler);
    return () => {
      // no explicit close as the socket wrapper reconnects
      // but allow GC by removing handler reference
      (socket as any).handler = () => {};
    };
  }, [pfId]);

  return (
    <div>
      <h3>Risk Metrics</h3>
      <ul>
        {points.map((p) => (
          <li key={p.date}>
            {p.date}: VaR {p.var.toFixed(4)} | CVaR {p.cvar.toFixed(4)} | Drawdown {p.drawdown.toFixed(4)}
          </li>
        ))}
      </ul>
    </div>
  );
};
