use ndarray::{Array1, ArrayView2};
use numpy::{PyReadonlyArray2};
use pyo3::prelude::*;

#[pyfunction]
fn risk_parity_weights(cov: PyReadonlyArray2<f64>) -> PyResult<Vec<f64>> {
    let cov: ArrayView2<f64> = cov.as_array();
    let n = cov.shape()[0];
    let mut w = Array1::from_elem(n, 1.0 / n as f64);

    for _ in 0..100 {
        let port_var = w.t().dot(&cov.dot(&w));
        let mrc = cov.dot(&w);
        let rc = &w * &mrc;
        let target = port_var / n as f64;
        let diff = &rc - target;
        if diff
            .mapv(f64::abs)
            .iter()
            .cloned()
            .fold(0.0_f64, f64::max)
            < 1e-8
        {
            break;
        }
        for i in 0..n {
            let denom = mrc[i] + 1e-12;
            w[i] -= diff[i] / denom;
            if w[i] < 0.0 {
                w[i] = 0.0;
            }
        }
        let sum_w: f64 = w.sum();
        if sum_w == 0.0 {
            w.fill(1.0 / n as f64);
        } else {
            w /= sum_w;
        }
    }
    Ok(w.to_vec())
}

#[pymodule]
fn risk_parity_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(risk_parity_weights, m)?)?;
    Ok(())
}
