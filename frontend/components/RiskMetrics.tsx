import React from 'react';

export interface RiskMetricsProps {
  varValue: number;
  cvarValue: number;
  drawdown: number;
}

const RiskMetrics: React.FC<RiskMetricsProps> = ({ varValue, cvarValue, drawdown }) => {
  return (
    <div>
      <h3>Risk Metrics</h3>
      <ul>
        <li>VaR: {varValue.toFixed(4)}</li>
        <li>CVaR: {cvarValue.toFixed(4)}</li>
        <li>Drawdown: {drawdown.toFixed(4)}</li>
      </ul>
    </div>
  );
};

export default RiskMetrics;
