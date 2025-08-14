use ndarray::{Array1, Array2, Axis};
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use nalgebra::{DMatrix, SymmetricEigen};

fn sample_cov(y: &Array2<f64>) -> Array2<f64> {
    let n = y.nrows() as f64;
    y.t().dot(y) / n
}

#[pyfunction]
fn ledoit_wolf_cov<'py>(py: Python<'py>, returns: PyReadonlyArray2<f64>) -> PyResult<&'py PyArray2<f64>> {
    let x = returns.as_array();
    let n = x.nrows();
    let p = x.ncols();

    // demean
    let mean = x.mean_axis(Axis(0)).unwrap();
    let x = &x - &mean.broadcast((n, p)).unwrap();

    // Helper matrices
    let x2 = x.mapv(|v| v * v);
    let emp_cov_trace = x2.sum_axis(Axis(0)) / n as f64;
    let mu = emp_cov_trace.sum() / p as f64;

    // beta_ and delta_
    let beta_mat = x2.t().dot(&x2);
    let beta_ = beta_mat.sum();
    let delta_mat = x.t().dot(&x);
    let delta_ = delta_mat.mapv(|v| v * v).sum() / (n as f64).powi(2);

    let beta = 1.0 / (p as f64 * n as f64) * (beta_ / n as f64 - delta_);
    let mut delta = delta_ - 2.0 * mu * emp_cov_trace.sum() + p as f64 * mu * mu;
    delta /= p as f64;
    let beta = beta.min(delta);
    let shrinkage = if beta == 0.0 { 0.0 } else { beta / delta };

    let mut emp_cov = sample_cov(&x.to_owned());
    emp_cov = emp_cov * (1.0 - shrinkage);
    for i in 0..p {
        emp_cov[[i, i]] += shrinkage * mu;
    }
    Ok(PyArray2::from_owned_array(py, emp_cov))
}

#[pyfunction]
fn pca_factor_cov<'py>(
    py: Python<'py>,
    returns: PyReadonlyArray2<f64>,
    n_components: usize,
) -> PyResult<&'py PyArray2<f64>> {
    let x = returns.as_array();
    let n = x.nrows();
    let p = x.ncols();

    let mean = x.mean_axis(Axis(0)).unwrap();
    let y = &x - &mean.broadcast((n, p)).unwrap();
    let s = sample_cov(&y.to_owned());

    // eigen decomposition
    let s_na = DMatrix::from_row_slice(p, p, s.as_slice().unwrap());
    let se = SymmetricEigen::new(s_na);
    let mut eig_pairs: Vec<(f64, Array1<f64>)> = se
        .eigenvalues
        .iter()
        .zip(se.eigenvectors.column_iter())
        .map(|(&val, vec)| (val, Array1::from_iter(vec.iter().cloned())))
        .collect();
    eig_pairs.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());

    let m = n_components.min(p);
    let mut loadings = Array2::<f64>::zeros((p, m));
    let mut factor_cov = Array2::<f64>::zeros((m, m));
    for i in 0..m {
        loadings.column_mut(i).assign(&eig_pairs[i].1);
        factor_cov[[i, i]] = eig_pairs[i].0;
    }

    let approx = loadings.dot(&factor_cov).dot(&loadings.t());
    let resid = &s - &approx;
    let mut diag = Array2::<f64>::zeros((p, p));
    for i in 0..p {
        diag[[i, i]] = resid[[i, i]];
    }
    let cov = approx + diag;

    Ok(PyArray2::from_owned_array(py, cov))
}

#[pymodule]
fn covariance_rs(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ledoit_wolf_cov, m)?)?;
    m.add_function(wrap_pyfunction!(pca_factor_cov, m)?)?;
    Ok(())
}
