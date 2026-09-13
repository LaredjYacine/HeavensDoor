from langchain.tools import tool
from .credentials import supabase_key , supabase_url, supabase_client
from .Search_function import hybridSearch



@tool
def Search(query:str):
    """ Use this When a users instructions are Vague This will make a HybridSearch to find the answer this will return an array with information from job_description column
    Args:
        query: what the user is looking for it has to be a vague expression such as (eg. Something focused on fixing database bottlenecks and optimizing slow queries rather than building frontend UI.)

    """
    result = hybridSearch(query)
    return result


@tool
def matching_candidates(query:str):
    """  Use this  tool when a user wants to check a certain criteria of candidates if they have certain requirements


Args:
    query : A Python expression string interacting with supabase_client supabase_client  and the supabase commands (eg . supabase_client.table("employees").select("*").execute()) )
    """
    global_env={
        "__builtins__": {},
        'supabase_client':supabase_client
    }
    if 'delete'or 'insert'or 'truncate' in query.lower():
        return  'Cannot delete insert or Truncate You can only View and fetch '

    result= eval(query,global_env)
    return result

@tool
def matching_jobs(query:str):
    """  Use this  tool when a user wants to check a certain jobs that match what the user wants

Args:
    query : A Python expression string interacting with supabase_client supabase_client  and the supabase commands (eg . supabase_client.table("employees").select("*").execute()) )
    """
    global_env={
        "__builtins__": {},
        'supabase_client':supabase_client
    }
    if 'delete'or 'insert'or 'truncate' in query.lower():
        return  'Cannot delete insert or Truncate You can only View and fetch '

    result= eval(query,global_env)
    return result


@tool
def get_tables():
    """
    Use this tool to get a list of all the tables in the database

    """
    try :
        result = supabase_client.rpc('get_tables').execute()
        return result
    except Exception as e:
        return str(e)

@tool
def table_schema(table_name:str):
    """
    use this tool when you want to know what are the columns of a table so you can understand what the user is trying to reference
    Args:
        query : a string that refers to the table name if you dont have the table name use get_tables tool

    """
    try :
        result = supabase_client.rpc('get_table_schema', {'table_name':table_name}).execute()
        return result
    except Exception as e:
        return str(e)




tools= [Search,table_schema,get_tables,matching_jobs,matching_candidates]
