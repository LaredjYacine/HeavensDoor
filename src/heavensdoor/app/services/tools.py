from langchain.tools import tool
from .credentials import supabase_key, supabase_url, supabase_client
from .Search_function import hybridSearch
from .credentials import hf_token
from .SSL_fix import Finetuned

@tool
def Search(query: str) -> str:
    """Use this ONLY to search the job postings database using a vague or fuzzy description
        of a job (not a general knowledge question, not career advice). This performs a HybridSearch
        over the job_description column and returns matching postings.

        Use this when the user is describing a job/role they want to find in the database, e.g.
        "something focused on fixing database bottlenecks" or "a remote-friendly frontend role."
        Do NOT use this for questions asking for advice, explanations, or general knowledge
        (e.g. "what skills do I need for X") — use default_Answer for those instead.

    Args:
        query: What the user is looking for. Must be a vague expression (e.g., "Something focused on fixing database bottlenecks").
    """
    try:
        result = hybridSearch(query)
        return str(result)
    except Exception as e:
        print('Error occurred on Search tool:', str(e))
        return f"Error: {str(e)}"

@tool
def matching_candidates(query: str) -> str:
    """Search for Candidates in the database by their preferred_job_role when an employer wants to look for people to hire.

    Args:
        query: A string that is the preferred job role.
    """
    try:
        response = supabase_client.table("Candidates").select("prefered_job_role,skills,degrees").ilike("prefered_job_role", f"%{query}%").execute()
        if response.data:
            return str(response.data)
        return "No candidates found matching that role."
    except Exception as e:
        print('Error occurred on matching_candidates tool:', str(e))
        return f"Error: {str(e)}"

@tool
def matching_jobs(query: str) -> str:
    """Search for jobs in the database by job title when a user wants a job or is looking for a job.

    Args:
        query: A string that is the name of the job title.
    """
    try:
        response = supabase_client.table("Jobs").select("job_name,skill_requirement,work_type, role ,company").ilike("job_name", f"%{query}%").execute()

        # FIX: Check response.data, not the response object itself
        if response.data:
            return str(response.data)
        return "No jobs found matching that title."
    except Exception as e:
        print('Error occurred on matching_jobs tool:', str(e))
        return f"Error: {str(e)}"

@tool
def get_tables(query: str = "") -> str:
    """Use this tool to get a list of all the tables in the database.

    Args:
        query: An optional dummy string (ignore this).
    """
    try:
        result = supabase_client.rpc('get_tables').execute()
        # FIX: Return result.data as a string
        return str(result.data)
    except Exception as e:
        print('Error occurred on get_tables tool:', str(e))
        return f"Error: {str(e)}"

@tool
def table_schema(table_name: str) -> str:
    """Use this tool when you want to know what the columns of a table are so you can understand what the user is trying to reference.

    Args:
        table_name: A string that refers to the exact table name. If you don't have the table name, use get_tables tool first.
    """
    try:
        result = supabase_client.rpc('get_table_schema', {'table_name': table_name}).execute()
        # FIX: Return result.data as a string
        return str(result.data)
    except Exception as e:
        print('Error occurred on table_schema tool:', str(e))
        return f"Error: {str(e)}"


@tool
def default_Answer(query:str):
    """ Use this for general knowledge questions, advice, explanations, or anything that is
        NOT a request to search/query the Jobs or Candidates database. Examples: "what skills are
        needed for backend development", "how do I write a good resume", "explain what a PM does."

        If the user's question doesn't require looking up specific job postings, candidates, or
        database records, use this tool rather than Search.

    Args:
        query: The user's request.
    """
    result = Finetuned.predict(user_text=query, api_name="/predict")
    return str(result)
tools = [default_Answer, Search, table_schema, get_tables, matching_jobs, matching_candidates]
