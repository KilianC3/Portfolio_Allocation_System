import React, { useRef } from 'react';
import { Line } from 'react-chartjs-2';
import type { ChartData, ChartOptions } from 'chart.js';
import { Chart as ChartJS } from 'chart.js/auto';
import { exportChart } from '../utils/export';

interface Props {
  dates: string[];
  returns: number[];
}

export const ReturnsChart: React.FC<Props> = ({ dates, returns }) => {
  const chartRef = useRef<ChartJS<'line'>>(null);

  const data: ChartData<'line'> = {
    labels: dates,
    datasets: [
      {
        label: 'Returns',
        data: returns,
        borderColor: 'rgba(75,192,192,1)',
        backgroundColor: 'rgba(75,192,192,0.2)',
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
  };

  const exportCSV = () => {
    const rows = [['date', 'return'], ...dates.map((d, i) => [d, returns[i]])];
    const csv = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'returns.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const exportPNG = () => {
    const chart = chartRef.current;
    if (!chart) return;
    exportChart(chart, 'returns.png');
  };

  return (
    <div>
      <h3>Daily Returns</h3>
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
