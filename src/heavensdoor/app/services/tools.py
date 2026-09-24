from langchain.tools import tool

from .credentials import supabase_client
from .Search_function import hybridSearch
from .SSL_fix import Finetuned


@tool
def HybridRag(query: str) -> str:
    """Use this ONLY when the user does NOT provide a clear job title, but instead
    describes responsibilities, technologies, or vague criteria (e.g., "something
    focused on fixing database bottlenecks" or "a remote-friendly frontend role").
    Do NOT use this if the user names a specific job title like "software engineer".

    Args:
        query: A description of duties, skills, or vague requirements.
    """
    try:
        result = hybridSearch(query)
        return str(result)
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
def matching_jobs(query: str, job_type: str | None = None) -> str:
    """Use this ONLY when the user explicitly names a specific job title or role
    (e.g., "Software Engineer", "Data Scientist", "Product Manager").
    This performs an exact/keyword search by job title.

    Args:
        query: The precise job title name extracted from the user prompt (e.g., "software engineer").
        job_type: The type of job to filter by (e.g., "full-time", "part-time").
    """
    try:
        if job_type is None:
            response = (
                supabase_client.table("Jobs")
                .select("job_name,skill_requirement,work_type, role ,company")
                .ilike("job_name", f"%{query}%")
                .execute()
            )
        else:
            response = (
                supabase_client.table("Jobs")
                .select("job_name,skill_requirement,work_type, role ,company")
                .ilike("job_name", f"%{query}%")
                .ilike("work_type", f"%{job_type}%")
                .execute()
            )

        if response.data:
            return str(response.data)
        return "No jobs found matching that title."
    except Exception as e:  # noqa: BLE001
        print("Error occurred on matching_jobs tool:", str(e))
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
    """Use this for general knowledge questions, advice, explanations, or anything that is
        NOT a request to search/query the Jobs or Candidates database. Examples: "what skills are
        needed for backend development", "how do I write a good resume", "explain what a PM does."

        If the user's question doesn't require looking up specific job postings, candidates, or
        database records, use this tool rather than Search.

    Args:
        query: The user's request.
    """
    result = Finetuned.predict(user_text=query, api_name="/predict")
    return str(result)


tools = [
    default_Answer,
    HybridRag,
    table_schema,
    get_tables,
    matching_jobs,
    matching_candidates,
]
