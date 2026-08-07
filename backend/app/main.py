from fastapi import FastAPI

app = FastAPI(
    title="NexHire Backend",
    version="1.0.0"
)

@app.get("/")
def home():
    return {"message": "NexHire Backend Running"}