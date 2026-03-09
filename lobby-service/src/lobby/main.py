import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lobby.routes.routes import router

app = FastAPI(title="auth-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("auth.main:app", host="0.0.0.0", port=8000, reload=True)
