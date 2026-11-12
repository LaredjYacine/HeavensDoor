from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from postgrest.exceptions import APIError
from pydantic import BaseModel, EmailStr
from supabase_auth.errors import AuthApiError, AuthInvalidCredentialsError
from supabase_auth.types import User

from ..services.credentials import supabase_client
from ..services.embedmodel import get_embedding_model

auth = APIRouter(prefix="/auth")
embedder = get_embedding_model()
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
    print(f"Token received: {token[:20]}..." if token else "No token")

    try:
        response = supabase_client.auth.get_user(token)
        if response is None or response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return response.user
    except (AuthApiError, AuthInvalidCredentialsError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


currentUser = Annotated[User, Depends(get_current_user)]


@auth.post("/apply_candidate")
def apply_candidate(candidate_info: CandidateSchema, currentuser: currentUser):
    try:
        id = currentuser.id
        data = (
            supabase_client.table("UsersCooldown")
            .select("Expired")
            .eq("id", id)
            .execute()
        )
        exist = data.data
        print(data)
        if exist and exist[0].get("Expired"):
            expired_str = str(exist[0].get("Expired"))
            expiration_date = date.fromisoformat(expired_str[:10])
            now = datetime.now(UTC).date()
            remaining_time = expiration_date - now

            days_left = remaining_time.days

            hours_left = remaining_time.seconds // 3600

            raise HTTPException(
                status_code=400,
                detail=f"You must wait {days_left} days and {hours_left} hours  ",
            )

        user_data = candidate_info.model_dump()
        if not user_data:
            raise HTTPException(status_code=400, detail="User data must not be empty ")
        embeded_fields = [
            str(user_data.get("skills")),
            str(user_data.get("education_institutions")),
            str(user_data.get("professional_comapany_names")),
            str(user_data.get("prefered_job_role")),
            str(user_data.get("job_position_name")),
            str(user_data.get("is_remote_eligible")),
            str(user_data.get("certification_skills")),
            str(user_data.get("certification_providers")),
        ]
        text_to_embed = " ".join(f for f in embeded_fields if f.strip())
        payload = {
            "Id": id,  # Or whatever your foreign key column name is in the Candidates table (e.g., "user_id")
            **user_data,
            "Embeddings": next(iter(embedder.embed([text_to_embed]))).tolist(),
        }

        response = supabase_client.table("Candidates").insert(payload).execute()
        response2 = supabase_client.table("UsersCooldown").insert({"id": id}).execute()
        print(response2.data)
        return {
            "message": "Application submitted successfully for 1 day ",
            "data": response.data,
        }
    except APIError as e:
        raise HTTPException(
            status_code=400, detail=f"failed Adding the User as a Candidate {e}"
        )


@auth.post("/sign_up")
def sign_up(userData: SignInSchema):
    try:
        response = supabase_client.auth.sign_up(
            {
                "email": userData.email,
                "password": userData.password,
            }
        )
        if response.user and not response.user.identities:
            raise HTTPException(
                status_code=400, detail="An account with this email already exists."
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
async def login(
    userData: SignInSchema,
):  # Annotated[OAuth2PasswordRequestForm, Depends()]):
    try:
        response = supabase_client.auth.sign_in_with_password(
            {"email": userData.email, "password": userData.password}
        )
        if not response:
            raise AuthInvalidCredentialsError("Couldn't return a resposne")
        return {
            "access_token": response.session.access_token
            if response.session
            else None,  # <-- Swagger UI needs this
            "token_type": "bearer",
            "user": response.user,
            "session": response.session,
            "message": "Login was successful.",
        }
    except AuthApiError:
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    except AuthInvalidCredentialsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@auth.get("/me")
def get_me(current_user: currentUser):
    return {"user": current_user}
