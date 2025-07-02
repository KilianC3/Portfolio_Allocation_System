import numpy as np, pandas as pd
from config import MIN_ALLOC, MAX_ALLOC
from logger import get_logger
_log = get_logger("alloc")
def _dd(series):
    curve=(1+series).cumprod()
    dd=curve/curve.cummax()-1
    return dd.tail(20).min()
def compute_weights(ret_df:pd.DataFrame,target_vol=0.10,lmb=0.8):
    r=ret_df.tail(20).mean(); s=ret_df.tail(20).std(ddof=0)
    score=np.power(np.clip(r/s.pow(2),0,None),lmb)
    if score.sum()==0: score+=1
    w=score/score.sum()
    dd=ret_df.apply(_dd); w.loc[dd<-0.06]*=0.5; w/=w.sum()
    cov=ret_df.tail(20).cov()*252
    port_vol=np.sqrt(w@cov@w)
    k=min(1.5, target_vol/port_vol)
    w*=k
    w=w.clip(lower=MIN_ALLOC, upper=MAX_ALLOC); w/=w.sum()
    _log.info({"weights":w.to_dict(),"vol":port_vol,"scale":k})
    return w.to_dict()
