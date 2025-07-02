import logging, json, datetime as dt
def _ser(rec):
    base = {"ts": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "lvl": rec.levelname.lower(),
            "mod": rec.name,
            "msg": rec.getMessage()}
    if rec.exc_info:
        base["exc"] = logging.Formatter().formatException(rec.exc_info)
    return json.dumps(base)

class _H(logging.StreamHandler):
    def emit(self, rec):
        self.stream.write(_ser(rec)+"\n"); self.flush()
def get_logger(name:str):
    lg = logging.getLogger(name)
    if not lg.handlers:
        lg.setLevel(logging.INFO)
        lg.addHandler(_H())
        lg.propagate=False
    return lg
