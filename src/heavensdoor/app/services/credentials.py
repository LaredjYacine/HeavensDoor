import dotenv
import os

dotenv.load_dotenv()

supabase_url: str|None = os.getenv('supabase_url')
supabase_key :str |None = os.getenv('supabase_Key')
