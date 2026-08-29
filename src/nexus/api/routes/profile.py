"""
NEXUS API — User Profile Management Endpoints.

Allows collecting and managing user profile details (name, age, gender) in the Supabase PostgreSQL database.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.database.engine import get_session
from nexus.database.models import User
from nexus.security.supabase_auth import SupabaseUser, get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])


class ProfileSetupRequest(BaseModel):
    name: str = Field(..., min_length=1, description="User's full name")
    age: int = Field(..., ge=1, le=120, description="User's age")
    gender: str = Field(..., description="User's gender (male/female/other)")


@router.post("/setup")
async def setup_profile(
    body: ProfileSetupRequest,
    current_supabase_user: SupabaseUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Save or update user details (name, age, gender) mapped to their Supabase user ID.
    """
    user_id = current_supabase_user.user_id

    async with get_session() as session:
        # Check if user already exists in the database
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Update profile details
            user.name = body.name
            user.age = body.age
            user.gender = body.gender
        else:
            # Create new user record
            user = User(
                id=user_id,
                name=body.name,
                age=body.age,
                gender=body.gender,
            )
            session.add(user)

        await session.flush()
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "profile": {
                "user_id": user_id,
                "name": user.name,
                "age": user.age,
                "gender": user.gender,
            },
        }


@router.get("/me")
async def get_profile(
    current_supabase_user: SupabaseUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Fetch the current user profile. Returns setup_required = True if the profile hasn't been completed.
    """
    user_id = current_supabase_user.user_id

    async with get_session() as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.name or user.age is None or not user.gender:
            return {
                "setup_required": True,
                "user_id": user_id,
                "email": current_supabase_user.email,
            }

        return {
            "setup_required": False,
            "profile": {
                "user_id": user_id,
                "email": current_supabase_user.email,
                "name": user.name,
                "age": user.age,
                "gender": user.gender,
            },
        }
