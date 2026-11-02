from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from supabase_auth.errors import AuthApiError, AuthInvalidCredentialsError

from ..services.credentials import supabase_client

auth = APIRouter(prefix="/auth")


class SignInSchema(BaseModel):
    email: EmailStr
    password: str


@auth.post("/sign_up")
def sign_up(userData: SignInSchema):
    try:
        response = supabase_client.auth.sign_up(
            {"email": userData.email, "password": userData.password}
        )
        return {
            "message": "Sign-up successful. Check your email for confirmation if enabled.",
            "user": response.user,
            "session": response.session,
        }
    except AuthApiError:
        # This catches incorrect passwords or missing accounts
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    except AuthInvalidCredentialsError as e:
        raise HTTPException(status_code=400, detail=e)


@auth.post("/login")
async def login(userData: SignInSchema):
    try:
        response = supabase_client.auth.sign_in_with_password(
            {"email": userData.email, "password": userData.password}
        )
        return {
            "message": "Login was  successful.",
            "user": response.user,
            "session": response.session,
        }
    except AuthApiError:
        # This catches incorrect passwords or missing accounts
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    except AuthInvalidCredentialsError as e:
        raise HTTPException(status_code=400, detail=e)
