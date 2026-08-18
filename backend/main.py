import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "students")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

pool = None

class Student(BaseModel):
    id: int | None = None
    name: str
    email: str
    major: str

class StudentCreate(BaseModel):
    name: str
    email: str
    major: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=2,
        max_size=10
    )
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            major VARCHAR(100) NOT NULL
        )
    """)
    yield
    await pool.close()

app = FastAPI(title="Student Manager API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/students")
async def list_students():
    rows = await pool.fetch("SELECT id, name, email, major FROM students ORDER BY id")
    return [dict(r) for r in rows]

@app.post("/students")
async def create_student(student: StudentCreate):
    try:
        row = await pool.fetchrow(
            "INSERT INTO students (name, email, major) VALUES ($1, $2, $3) RETURNING id, name, email, major",
            student.name, student.email, student.major
        )
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Email already exists")

@app.get("/students/{student_id}")
async def get_student(student_id: int):
    row = await pool.fetchrow("SELECT id, name, email, major FROM students WHERE id = $1", student_id)
    if not row:
        raise HTTPException(status_code=404, detail="Student not found")
    return dict(row)

@app.put("/students/{student_id}")
async def update_student(student_id: int, student: StudentCreate):
    try:
        row = await pool.fetchrow(
            "UPDATE students SET name=$1, email=$2, major=$3 WHERE id=$4 RETURNING id, name, email, major",
            student.name, student.email, student.major, student_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Student not found")
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Email already exists")

@app.delete("/students/{student_id}")
async def delete_student(student_id: int):
    result = await pool.execute("DELETE FROM students WHERE id = $1", student_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted"}
