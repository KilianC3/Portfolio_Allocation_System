async function loadDashboard() {
  const urlParams = new URLSearchParams(window.location.search);
  const pfId = urlParams.get('pf_id') || '';
  if (!pfId) return;
  const resp = await fetch(`/dashboard/${pfId}`);
  const data = await resp.json();

  const dates = data.returns.map(r => r.date);
  const vals = data.returns.map(r => r.value);
  const returnsCtx = document.getElementById('returnsChart').getContext('2d');
  const returnsChart = new Chart(returnsCtx, {
    type: 'line',
    data: { labels: dates, datasets: [{ label: 'Returns', data: vals }] }
  });

  document.getElementById('downloadReturns').onclick = () => {
    const a = document.createElement('a');
    a.href = returnsChart.toBase64Image();
    a.download = 'returns.png';
    a.click();
  };

  document.getElementById('exportReturns').onclick = () => {
    let csv = 'date,return\n';
    data.returns.forEach(r => { csv += `${r.date},${r.value}\n`; });
    const blob = new Blob([csv], {type: 'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'returns.csv';
    a.click();
  };

  const expLabels = Object.keys(data.exposures);
  const expVals = Object.values(data.exposures);
  const expCtx = document.getElementById('exposureChart').getContext('2d');
  const exposureChart = new Chart(expCtx, {
    type: 'pie',
    data: { labels: expLabels, datasets: [{ data: expVals }] }
  });

  document.getElementById('downloadExposure').onclick = () => {
    const a = document.createElement('a');
    a.href = exposureChart.toBase64Image();
    a.download = 'exposures.png';
    a.click();
  };

  document.getElementById('alpha').textContent = data.alpha !== null && data.alpha !== undefined ? data.alpha.toFixed(4) : '';
  document.getElementById('beta').textContent = data.beta !== null && data.beta !== undefined ? data.beta.toFixed(4) : '';
}

window.addEventListener('load', loadDashboard);
