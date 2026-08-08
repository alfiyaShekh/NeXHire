from fastapi import FastAPI
import uvicorn

app = FastAPI(
    title="NexHire Backend",
    version="1.0.0"
)

@app.get("/")
def home():
    return {"message": "NexHire Backend Running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)