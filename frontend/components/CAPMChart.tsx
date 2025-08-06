import React, { useRef } from 'react';
import { Line } from 'react-chartjs-2';
import type { ChartData, ChartOptions } from 'chart.js';
import { Chart as ChartJS } from 'chart.js/auto';
import { exportChart } from '../utils/export';

interface Point {
  date: string;
  expected: number;
  actual: number;
}

export const CAPMChart: React.FC<{ points: Point[] }> = ({ points }) => {
  const chartRef = useRef<ChartJS<'line'>>(null);

  const data: ChartData<'line'> = {
    labels: points.map((p) => p.date),
    datasets: [
      {
        label: 'Expected',
        data: points.map((p) => p.expected),
        borderColor: 'rgba(255,159,64,1)',
        backgroundColor: 'rgba(255,159,64,0.2)',
      },
      {
        label: 'Actual',
        data: points.map((p) => p.actual),
        borderColor: 'rgba(54,162,235,1)',
        backgroundColor: 'rgba(54,162,235,0.2)',
      },
    ],
  };

  const options: ChartOptions<'line'> = { responsive: true };

  const exportCSV = () => {
    const rows = [
      ['date', 'expected', 'actual'],
      ...points.map((p) => [p.date, p.expected, p.actual]),
    ];
    const csv = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'capm.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportPNG = () => {
    const chart = chartRef.current;
    if (!chart) return;
    exportChart(chart, 'capm.png');
  };

  return (
    <div>
      <h3>CAPM Metrics</h3>
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
