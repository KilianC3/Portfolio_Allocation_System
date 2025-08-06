import React, { useState } from "react";

interface Props {
  pfId: string;
  weights: Record<string, number>;
}

const AllocationControls: React.FC<Props> = ({ pfId, weights }) => {
  const [strategy, setStrategy] = useState("tangency");
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
          <option value="tangency">Tangency</option>
          <option value="risk_parity">Risk Parity</option>
          <option value="min_variance">Min Variance</option>
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
