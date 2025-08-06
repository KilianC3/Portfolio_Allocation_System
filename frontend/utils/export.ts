import type { Chart } from 'chart.js';

/**
 * Trigger a PNG download of a Chart.js instance.
 */
export function exportChart(chart: Chart, filename: string): void {
  const link = document.createElement('a');
  link.href = chart.toBase64Image();
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
