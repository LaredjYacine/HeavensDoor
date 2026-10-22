import re
from difflib import SequenceMatcher

from langchain.tools import tool

from .credentials import supabase_client
from .Search_function import hybridSearch
from .SSL_fix import Finetuned


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(inc|llc|ltd|gmbh|corp|co|technologies|technology)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


TEXT_FILTERS = ("company", "work_type", "location", "role")


def matches(row, filters: dict):
    for f in TEXT_FILTERS:
        want = filters.get(f)
        if not want:
            continue
        want = norm(want)
        have = norm(row.get(f))
        if want not in have and SequenceMatcher(None, have, want).ratio() < 0.70:
            return False
    return True


@tool
def HybridRag(
    query: str,
    work_type: str | None = None,
    company: str | None = None,
    role: str | None = None,
) -> str:
    """Use this to find a job based on the users query ".

    Args:
        query: A description of duties, skills, or vague requirements.
        work_type: is wether its Contractor , Full Time , Intern, Volunteer..etc
        company: is the name of the company .
        role : consists of the role of the job such as : Mid senior , Associate, Senior , ManagerSenior , Entery-level, Manager,Executive..etc
    """
    try:
        seen = set()
        filters = {
            "work_type": work_type,
            "company": company,
            "role": role,
        }
        accepted_jobs = []
        rows = hybridSearch(query)

        for row in rows:
            result = matches(row, filters)
            print(result)
            if result and row["id"] not in seen:
                seen.add(row["id"])
                accepted_jobs.append(row["job_description"])
            continue
        if accepted_jobs:
            return str(accepted_jobs[:5])
        return (
            "didnt find any matches for the requirements of the  job   you described "
        )
    except Exception as e:  # noqa: BLE001
        print("Error occurred on Search tool:", str(e))
        return f"Error: {e!s}"


@tool
def matching_candidates(query: str) -> str:
    """Search for Candidates in the database by their preferred_job_role when an employer wants to look for people to hire.

    Args:
        query: A string that is the preferred job role.
    """
    try:
        response = (
            supabase_client.table("Candidates")
            .select("prefered_job_role,skills,degrees")
            .ilike("prefered_job_role", f"%{query}%")
            .execute()
        )
        if response.data:
            return str(response.data)
        return "No candidates found matching that role."
    except Exception as e:  # noqa: BLE001
        print("Error occurred on matching_candidates tool:", str(e))
        return f"Error: {e!s}"


@tool
def get_tables(query: str = "") -> str:
    """Use this tool to get a list of all the tables in the database.

    Args:
        query: An optional dummy string (ignore this).
    """
    try:
        result = supabase_client.rpc("get_tables").execute()
        # FIX: Return result.data as a string
        return str(result.data)
    except Exception as e:  # noqa: BLE001
        print("Error occurred on get_tables tool:", str(e))
        return f"Error: {e!s}"


@tool
def table_schema(table_name: str) -> str:
    """Use this tool when you want to know what the columns of a table are so you can understand what the user is trying to reference.

    Args:
        table_name: A string that refers to the exact table name. If you don't have the table name, use get_tables tool first.
    """
    try:
        result = supabase_client.rpc(
            "get_table_schema", {"table_name": table_name}
        ).execute()
        # FIX: Return result.data as a string
        return str(result.data)
    except Exception as e:  # noqa: BLE001
        print("Error occurred on table_schema tool:", str(e))
        return f"Error: {e!s}"


@tool
def default_Answer(query: str):
    """This gives you access to A finetuned Model Use it when Needed for an Advice or When no tool is needed but requires information about certain Jobs or resumes

    Args:
        query: The user's request.
    """
    if Finetuned is None:
        return ["Fine tuned model was Not found Sorry for inconvenience"]
    result = Finetuned.predict(user_text=query, api_name="/predict")
    return str(result)


tools = [
    default_Answer,
    HybridRag,
    table_schema,
    get_tables,
    matching_candidates,
]
