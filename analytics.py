import numpy as np, pandas as pd, math, scipy.stats as st
def sharpe(r:pd.Series,rf=0.0):
    if r.std(ddof=0)==0: return 0.0
    return (r.mean()-rf)/r.std(ddof=0)*math.sqrt(252)
def var_cvar(r:pd.Series, level=0.95):
    var=np.quantile(r,1-level)
    cvar=r[r<=var].mean()
    return var,cvar
