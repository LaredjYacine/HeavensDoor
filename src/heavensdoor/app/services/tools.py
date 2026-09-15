from langchain.tools import tool
from .credentials import supabase_key, supabase_url, supabase_client
from .Search_function import hybridSearch

@tool
def Search(query: str) -> str:
    """Use this when a user's instructions are vague. This makes a HybridSearch to find the answer.
    It returns an array with information from the job_description column.

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

tools = [Search, table_schema, get_tables, matching_jobs, matching_candidates]
