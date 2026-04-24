import uvicorn #type: ignore
from fastapi import FastAPI #type: ignore
from fastapi.staticfiles import StaticFiles  #type: ignore
import logging
import user_templates

app = FastAPI(title="Monk Categories API")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(user_templates.router)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=True) 