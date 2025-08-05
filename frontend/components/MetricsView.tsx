import { useEffect, useState } from "react";
import { metricsSocket } from "../utils/socket";

export default function MetricsView() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    metricsSocket.connect();
    metricsSocket.on((d) => setData(d));
  }, []);

  if (!data) return <div>No metrics yet</div>;
  return (
    <div>
      <div>Return: {data.ret}</div>
      <div>Win Rate: {data.win_rate}</div>
    </div>
  );
}
