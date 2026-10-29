import os

import dotenv
from apify_client import ApifyClient
from apify_client.errors import RateLimitError
from supabase import create_client


from heavensdoor.app.services.embedmodel import get_embedding_model

embedding_model = get_embedding_model()
dotenv.load_dotenv()
apikey = os.environ["apify"]
# Initialize the ApifyClient with your Apify API token
# Replace '<YOUR_API_TOKEN>' with your token.
client = ApifyClient(apikey)
supabase_client = create_client(os.environ["supabase_url"], os.environ["supabase_Key"])

# Prepare the Actor input
run_input = {
    "startUrls": [{"url": "https://emploitic.com/offres-d-emploi"}],
    "maxItems": 30,
    "maxPages": 2,
}

# Run the Actor and wait for it to finish
try:
    run = client.actor("scraper_guru/algeria-emploitic-jobs-scraper").call(
        run_input=run_input
    )
    for item in client.dataset(run.default_dataset_id).iterate_items():
        job_name = item.get("job_title") or ""
        company = item.get("company_name") or ""
        work_type = item.get("employment_type") or ""
        salary = item.get("salary") or ""
        location = item.get("location") or "dz"
        job_description = item.get("description") or ""
        job_link = item.get("job_url") or ""
        expiry_date = item.get("valid_through") or item.get("date_posted") or None

        role_parts = []
        if item.get("job_levels"):
            role_parts.extend(item["job_levels"])
        if item.get("experience_years"):
            role_parts.extend(item["experience_years"])
        role = ", ".join(role_parts)

        skill_parts = []
        if item.get("professions"):
            skill_parts.extend(item["professions"])
        if item.get("tags"):
            skill_parts.extend(item["tags"][:5])
        skill_requirement = ", ".join(skill_parts)

        embedding = next(iter(embedding_model.embed([job_description])))

        payload = {
            "job_name": job_name,
            "role": role,
            "location": location,
            "company": company,
            "work_type": work_type,
            "salary": salary,
            "skill_requirement": skill_requirement,
            "job_description": job_description,
            "embeddings": embedding.tolist(),
            "contact": job_link,
            "Expired_at": expiry_date,
        }
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
        supabase_client.table("Jobs").insert(payload).execute()
        print(f"Inserted: {payload}")
except RateLimitError as e:
    print(f"error occured : {e}")

# Fetch and print Actor results from the run's dataset (if there are any)
