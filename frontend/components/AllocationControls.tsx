import React, { useState } from "react";

interface Props {
  pfId: string;
  weights: Record<string, number>;
}

const AllocationControls: React.FC<Props> = ({ pfId, weights }) => {
  const [strategy, setStrategy] = useState("max_sharpe");
  const [risk, setRisk] = useState(0.11);

  const submit = async () => {
    await fetch(`/portfolios/${pfId}/weights`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weights, strategy, risk_target: risk })
    });
  };

  return (
    <div>
      <label>
        Strategy:
        <select value={strategy} onChange={e => setStrategy(e.target.value)}>
          <option value="max_sharpe">Max Sharpe</option>
          <option value="risk_parity">Risk Parity</option>
          <option value="min_variance">Min Variance</option>
          <option value="saa">Strategic (SAA)</option>
          <option value="taa">Tactical (TAA)</option>
          <option value="dynamic">Dynamic</option>
        </select>
      </label>
      <label>
        Risk Target:
        <input
          type="number"
          step="0.01"
          value={risk}
          onChange={e => setRisk(parseFloat(e.target.value))}
        />
      </label>
      <button onClick={submit}>Save</button>
    </div>
  );
};

export default AllocationControls;
