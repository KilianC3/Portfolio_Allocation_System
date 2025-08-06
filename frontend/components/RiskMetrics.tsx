import React, { useEffect, useRef, useState } from 'react';
import { Line } from 'react-chartjs-2';
import type { ChartData, ChartOptions } from 'chart.js';
import { Chart as ChartJS } from 'chart.js/auto';
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
  const chartRef = useRef<ChartJS<'line'>>(null);

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

  const data: ChartData<'line'> = {
    labels: points.map((p) => p.date),
    datasets: [
      {
        label: 'VaR',
        data: points.map((p) => p.var),
        borderColor: 'rgba(255, 99, 132, 1)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
      },
      {
        label: 'CVaR',
        data: points.map((p) => p.cvar),
        borderColor: 'rgba(54, 162, 235, 1)',
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
      },
      {
        label: 'Drawdown',
        data: points.map((p) => p.drawdown),
        borderColor: 'rgba(255, 206, 86, 1)',
        backgroundColor: 'rgba(255, 206, 86, 0.2)',
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        ticks: {
          callback: (val: any) => val.toString(),
        },
      },
    },
  };

  const exportCSV = () => {
    const rows = [
      ['date', 'var', 'cvar', 'drawdown'],
      ...points.map((p) => [p.date, p.var, p.cvar, p.drawdown]),
    ];
    const csv = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `risk_metrics_${pfId}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportPNG = () => {
    const chart = chartRef.current;
    if (!chart) return;
    const link = document.createElement('a');
    link.href = chart.toBase64Image();
    link.setAttribute('download', `risk_metrics_${pfId}.png`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      <h3>Risk Metrics</h3>
      <Line ref={chartRef} data={data} options={options} />
      <div style={{ marginTop: '1rem' }}>
        <button onClick={exportCSV} style={{ marginRight: '0.5rem' }}>
          Export CSV
        </button>
        <button onClick={exportPNG}>Export PNG</button>
      </div>
    </div>
  );
};
