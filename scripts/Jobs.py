import os
from datetime import UTC, datetime

import dotenv
import httpx
import requests
from dateutil.relativedelta import relativedelta
from postgrest.exceptions import APIError
from supabase import create_client

from heavensdoor.app.services.embedmodel import get_embedding_model

dotenv.load_dotenv()
supabase_client = create_client(os.environ["supabase_url"], os.environ["supabase_Key"])

response = requests.get(
    "https://himalayas.app/jobs/api/search?country=dz&worldwide=true&sort=recent"
)
response2 = requests.get("https://jobicy.com/api/v2/remote-jobs?count=200&geo=anywhere")

Jobicy_Jobs = response2.json()
embedder = get_embedding_model()
data = response.json()
data_topush = []
for (
    job,
    task,
) in zip(data["jobs"], Jobicy_Jobs["jobs"]):
    # -------- for Himalayas api --------------------------------

    job_description = job["description"]

    exist = (
        supabase_client.table("Jobs")
        .select("job_description")
        .eq("job_description", job_description)
        .limit(1)
        .execute()
    )

    # --------------- for Jobicy -----------------------------------------
    task_job_description = task["jobDescription"]

    task_exist = (
        supabase_client.table("Jobs")
        .select("job_description")
        .eq("job_description", task_job_description)
        .limit(1)
        .execute()
    )

    try:
        if len(exist.data) > 0:
            print("already exist")

        else:
            job_name = job["title"]
            role = ",".join([seniority for seniority in job["seniority"]])
            company = job["companyName"]
            work_type = job["employmentType"]
            salary = f"min : {job['minSalary']} . max : {job['maxSalary']}"
            skill_requirement = ",".join([skills for skills in job["categories"]])
            job_link = job["applicationLink"]

            expiry_timestamp = job["expiryDate"]
            expiry_date = datetime.fromtimestamp(expiry_timestamp, tz=UTC).isoformat()
            embeddings = next(iter(embedder.embed([job_description])))

            payload = {
                "job_name": job_name,
                "role": role,
                "company": company,
                "work_type": work_type,
                "salary": salary,
                "skill_requirement": skill_requirement,
                "job_description": job_description,
                "embeddings": embeddings.tolist(),
                "contact": job_link,
                "Expired_at": expiry_date,  # Matches your Supabase timestamptz column
            }
            supabase_client.table("Jobs").insert(payload).execute()
            print("Sucessfully Added Himalaya job to the database")
        if len(task_exist.data) > 0:
            print("already exist")
        else:
            task_name = task["jobTitle"]
            task_role = task.get("jobLevel", "")
            task_company = task["companyName"]
            task_work_type = ",".join([type for type in task["jobType"]])
            task_skill_requirement = ",".join(
                [skill for skill in task.get("jobIndustry", "")]
            )
            task_link = task["url"]

            # Expiry date: 1 month after Jobicy's pubDate string
            pub_date = datetime.fromisoformat(task["pubDate"])
            task_expiry_date = (pub_date + relativedelta(months=1)).isoformat()
            task_embeddings = next(iter(embedder.embed([task_job_description])))
            task_payload = {
                "job_name": task_name,
                "role": task_role,
                "company": task_company,
                "work_type": task_work_type,
                "skill_requirement": task_skill_requirement,
                "job_description": task_job_description,
                "embeddings": task_embeddings.tolist(),
                "Expired_at": task_expiry_date,
                "contact": task_link,
                # 1 month after pubDate
            }
            supabase_client.table("Jobs").insert(task_payload).execute()
            print("Sucessfully Added Jobicy job to the database")

    except httpx.RequestError as e:
        print("Network Error Occured ", e)
    except APIError as e:
        print("Api error ", e)
