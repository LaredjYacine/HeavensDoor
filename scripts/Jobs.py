import requests

response = requests.get(
    "https://himalayas.app/jobs/api/search?country=dz&worldwide=true&sort=recent"
)

data = response.json()
for job in data["jobs"]:
    job_name = job["title"]
    role = "".join([seniority for seniority in job["seniority"]])
    company = job["companyName"]
    work_type = job["employmentType"]
    salary = f"min : {job['minSalary']} . max : {job['maxSalary']}"
