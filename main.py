from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Server is running successfully 🚀"}

@app.get("/hello")
def hello():
    return {"message": "Hello from MedBill Guard AI"}
