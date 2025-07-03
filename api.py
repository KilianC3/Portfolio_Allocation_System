from fastapi import FastAPI, Header, HTTPException, Depends
from database import pf_coll
from config import API_KEY

app = FastAPI()


def verify_api_key(x_api_key: str | None = Header(default=None)):
    """Validate the API key from the ``x-api-key`` header."""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/ping")
def ping(dep: None = Depends(verify_api_key)):
    """Basic health check."""
    return {"status": "ok"}


@app.get("/portfolios")
def list_portfolios(dep: None = Depends(verify_api_key)):
    """Return all portfolio names."""
    names = [p.get("name") for p in pf_coll.find({}, {"name": 1})]
    return {"portfolios": names}
