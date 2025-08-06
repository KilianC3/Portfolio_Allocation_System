import React, { useRef } from 'react';
import { Bar } from 'react-chartjs-2';
import type { ChartData, ChartOptions } from 'chart.js';
import { Chart as ChartJS } from 'chart.js/auto';
import { exportChart } from '../utils/export';

interface Props {
  sectors: { [key: string]: number };
}

export const SectorWeights: React.FC<Props> = ({ sectors }) => {
  const chartRef = useRef<ChartJS<'bar'>>(null);
  const labels = Object.keys(sectors);
  const weights = Object.values(sectors);

  const data: ChartData<'bar'> = {
    labels,
    datasets: [
      {
        label: 'Weight',
        data: weights,
        backgroundColor: 'rgba(153,102,255,0.5)',
      },
    ],
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    scales: { y: { beginAtZero: true } },
  };

  const exportCSV = () => {
    const rows = [['sector', 'weight'], ...labels.map((s, i) => [s, weights[i]])];
    const csv = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'sectors.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportPNG = () => {
    const chart = chartRef.current;
    if (!chart) return;
    exportChart(chart, 'sectors.png');
  };

  return (
    <div>
      <h3>Sector Weights</h3>
      <Bar ref={chartRef} data={data} options={options} />
      <div style={{ marginTop: '1rem' }}>
        <button onClick={exportCSV} style={{ marginRight: '0.5rem' }}>
          Export CSV
        </button>
        <button onClick={exportPNG}>Export PNG</button>
      </div>
    </div>
  );
};
