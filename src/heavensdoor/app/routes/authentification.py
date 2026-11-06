from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from postgrest.exceptions import APIError
from pydantic import BaseModel, EmailStr
from supabase_auth.errors import AuthApiError, AuthInvalidCredentialsError

from ..services.credentials import supabase_client

auth = APIRouter(prefix="/auth")

oauth2_schema = OAuth2PasswordBearer(tokenUrl="/auth/login")


class CandidateSchema(BaseModel):
    skills: str
    degrees: str | None
    education_institutions: str | None
    professional_comapany_names: str | None
    certification_skills: str | None
    certification_providers: str
    job_position_name: str
    prefered_job_role: str
    languages: str
    location: str
    is_remote_eligible: bool
    Name: str


class SignInSchema(BaseModel):
    email: EmailStr
    password: str


def get_current_user(token: str = Depends(oauth2_schema)):

    try:
        response = supabase_client.auth.get_user(token)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User cant be found "
            )
        user = response.user
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User cant be found "
            )

        return {"status": "SUCCESS", "data": user}
    except AuthApiError as e:
        return {"status": "FAILED", "error": e}


currentUser = Annotated[dict, Depends(get_current_user)]


@auth.post("/apply_candidate")
def apply_candidate(candidate_info: CandidateSchema, currentuser: currentUser):
    try:
        id = currentuser.get("id")
        print("this is the currentuser", currentuser)
        user_data = candidate_info.model_dump()
        payload = {
            "Id": id,  # Or whatever your foreign key column name is in the Candidates table (e.g., "user_id")
            **user_data,
        }
        response = supabase_client.table("Candidates").insert(payload).execute()
        return {"message": "Application submitted successfully", "data": response.data}
    except APIError as e:
        raise HTTPException(
            status_code=400, detail=f"failed Adding the User as a Candidate {e}"
        )


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
async def login(userData: Annotated[OAuth2PasswordRequestForm, Depends()]):
    try:
        response = supabase_client.auth.sign_in_with_password(
            {"email": userData.username, "password": userData.password}
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
