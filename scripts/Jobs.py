import os
from datetime import UTC, datetime

import dotenv
import httpx
import requests
from postgrest.exceptions import APIError
from supabase import create_client

from heavensdoor.app.services.embedmodel import get_embedding_model

dotenv.load_dotenv()
supabase_client = create_client(os.environ["supabase_url"], os.environ["supabase_Key"])

response = requests.get(
    "https://himalayas.app/jobs/api/search?country=dz&worldwide=true&sort=recent"
)
embedder = get_embedding_model()
data = response.json()
data_topush = []
for job in data["jobs"]:
    job_name = job["title"]
    role = "".join([seniority for seniority in job["seniority"]])
    company = job["companyName"]
    work_type = job["employmentType"]
    salary = f"min : {job['minSalary']} . max : {job['maxSalary']}"
    skill_requirement = "".join([skills for skills in job["categories"]])
    job_description = job["description"]
    embeddings = next(iter(embedder.embed([job_description])))
    expiry_timestamp = job["expiryDate"]
    expiry_date = datetime.fromtimestamp(expiry_timestamp, tz=UTC).isoformat()
    exist = (
        supabase_client.table("Jobs")
        .select("job_description")
        .eq("job_description", job_description)
        .limit(1)
        .execute()
    )

    if len(exist.data) > 0:
        print("already exist")
        continue
    try:
        payload = {
            "job_name": job_name,
            "role": role,
            "company": company,
            "work_type": work_type,
            "salary": salary,
            "skill_requirement": skill_requirement,
            "job_description": job_description,
            "embeddings": embeddings.tolist(),
            "Expired_at": expiry_date,  # Matches your Supabase timestamptz column
        }
        supabase_client.table("Jobs").insert(payload).execute()
        print("Sucessfully Added to the database")

    except httpx.RequestError as e:
        print("Network Error Occured ", e)
    except APIError as e:
        print("Api error ", e)
