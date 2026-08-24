from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_group_member
from app.db.session import get_db_session
from app.models import User
from app.schemas.groups import (
    AddGroupMemberRequest,
    GroupCreateRequest,
    GroupDetailResponse,
    GroupMemberResponse,
    GroupResponse,
)
from app.services.groups import (
    CannotRemoveGroupOwnerError,
    GroupDetails,
    GroupMemberNotFoundError,
    GroupNotFoundError,
    GroupOwnerRequiredError,
    MemberAlreadyExistsError,
    MemberHasNonzeroBalanceError,
    MemberUserNotFoundError,
    add_group_member,
    create_group,
    delete_group,
    get_group_details,
    list_groups_for_user,
    remove_group_member,
)


router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group_endpoint(
    request: GroupCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GroupResponse:
    group = create_group(session, current_user.id, request.name)
    return GroupResponse.model_validate(group)


@router.get("", response_model=list[GroupResponse])
def list_groups_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[GroupResponse]:
    return [
        GroupResponse.model_validate(group)
        for group in list_groups_for_user(session, current_user.id)
    ]


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group_endpoint(
    group_id: int,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GroupDetailResponse:
    del current_user
    try:
        details = get_group_details(session, group_id)
    except GroupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        ) from error
    return _group_detail_response(details)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_endpoint(
    group_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    try:
        delete_group(session, group_id, current_user.id)
    except GroupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        ) from error
    except GroupOwnerRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can delete this group",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_group_member_endpoint(
    group_id: int,
    request: AddGroupMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GroupMemberResponse:
    try:
        membership = add_group_member(session, group_id, current_user.id, request.email)
    except GroupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        ) from error
    except GroupOwnerRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can add members",
        ) from error
    except MemberUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered user exists with this email",
        ) from error
    except MemberAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this group",
        ) from error

    return GroupMemberResponse(
        id=membership.user.id,
        name=membership.user.name,
        email=membership.user.email,
        joined_at=membership.joined_at,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_group_member_endpoint(
    group_id: int,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    try:
        remove_group_member(session, group_id, current_user.id, user_id)
    except GroupNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        ) from error
    except GroupOwnerRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can remove members",
        ) from error
    except CannotRemoveGroupOwnerError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The group owner cannot be removed",
        ) from error
    except GroupMemberNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this group",
        ) from error
    except MemberHasNonzeroBalanceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member has a non-zero balance and cannot be removed",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _group_detail_response(details: GroupDetails) -> GroupDetailResponse:
    return GroupDetailResponse(
        id=details.group.id,
        name=details.group.name,
        owner_id=details.group.owner_id,
        created_at=details.group.created_at,
        members=[
            GroupMemberResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                joined_at=membership.joined_at,
            )
            for membership, user in details.members
        ],
    )
