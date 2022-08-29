"""Utility functions for creation of routes and responses."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from fhir.resources.bundle import Bundle
from fhir.resources.operationoutcome import OperationOutcome
from fhir.resources.resource import Resource

from . import status
from .interactions import ResourceType, SearchTypeInteraction, TypeInteraction


def make_operation_outcome(
    severity: str, code: str, details_text: str
) -> OperationOutcome:
    """Create a simple OperationOutcome given a severity, code, and details."""
    return OperationOutcome(
        **{
            "issue": [
                {
                    "severity": severity,
                    "code": code,
                    "details": {"text": details_text},
                }
            ]
        }
    )


@dataclass
class FormatParameters:
    format: str = "application/fhir+json"
    pretty: bool = False

    _CONTENT_TYPES: ClassVar = {
        "json": "application/fhir+json",
        "application/json": "application/fhir+json",
        "application/fhir+json": "application/fhir+json",
        "xml": "application/fhir+xml",
        "text/xml": "application/fhir+xml",
        "application/xml": "application/fhir+xml",
        "application/fhir+xml": "application/fhir+xml",
    }

    @classmethod
    def from_request(
        cls, request: Request, raise_exception: bool = True
    ) -> "FormatParameters":
        """
        Parse the _format and _pretty query parameters.

        The value for format is first obtained from the Accept header, and if not specified there is
        obtained from the _format query parameter.
        """
        format_ = cls.format_from_accept_header(request)

        try:
            if not format_:
                format_ = cls._CONTENT_TYPES[
                    request.query_params.get("_format", "json")
                ]
        except KeyError:
            if raise_exception:
                from .exceptions import FHIRGeneralError

                raise FHIRGeneralError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    severity="error",
                    code="structure",
                    details_text="Invalid response format specified for '_format' parameter",
                )
            else:
                format_ = "application/fhir+json"

        return cls(
            format=format_,  # type: ignore
            pretty=request.query_params.get("_pretty", "false") == "true",
        )

    @classmethod
    def format_from_accept_header(cls, request: Request) -> str | None:
        if request.method == "POST":
            for content_type in request.headers.getlist("Accept"):
                if content_type_normalized := cls._CONTENT_TYPES.get(content_type):
                    return content_type_normalized

        return None


def format_response(
    resource: Resource | None,
    response: Response | None = None,
    status_code: int | None = None,
    format_parameters: FormatParameters = FormatParameters(),
) -> Resource | Response:
    """
    Return a response with the proper formatting applied.

    This function provides a response in JSON or XML format that has been prettified if requested.

    There are six scenarios that are handled:
    1. Null resource (when there is no body -- no handling required)
    1. Pretty JSON
    2. Minified JSON with a status code (mainly for errors)
    3. Minified JSON with no specified status code (usually the default)
    4. Pretty XML
    5. Minified XML
    """
    if not resource:
        assert (
            response is not None
        ), "Response object must be provided for a null resource"
        response.headers["Content-Type"] = format_parameters.format
        return resource

    if format_parameters.format == "application/fhir+json":
        if format_parameters.pretty:
            return Response(
                content=resource.json(indent=2, separators=(", ", ": ")),
                status_code=status_code or status.HTTP_200_OK,
                media_type=format_parameters.format,
            )
        else:
            if status_code:
                return JSONResponse(
                    content=resource.dict(),
                    status_code=status_code,
                    media_type=format_parameters.format,
                )
            else:
                assert (
                    response is not None
                ), "Response object or status code must be provided for non-pretty JSON responses"
                response.headers["Content-Type"] = format_parameters.format
                return resource
    else:
        return Response(
            content=resource.xml(pretty_print=format_parameters.pretty),
            status_code=status_code or status.HTTP_200_OK,
            media_type=format_parameters.format,
        )


def create_route_args(interaction: TypeInteraction[ResourceType]) -> dict[str, Any]:
    """Provide arguments for creation of a FHIR create API route."""
    resource_type_str = interaction.resource_type.get_resource_type()

    return {
        "path": f"/{resource_type_str}",
        "response_model": interaction.resource_type,
        "status_code": status.HTTP_201_CREATED,
        "tags": [f"Type:{interaction.resource_type.get_resource_type()}"],
        "summary": f"{resource_type_str} {interaction.label()}",
        "description": f"The {resource_type_str} create interaction creates a new "
        f"{resource_type_str} resource in a server-assigned location.",
        "responses": _responses(
            interaction, _created, _bad_request, _unauthorized, _unprocessable_entity
        ),
        "response_model_exclude_none": True,
        **interaction.route_options,
    }


def read_route_args(interaction: TypeInteraction[ResourceType]) -> dict[str, Any]:
    """Provide arguments for creation of a FHIR read API route."""
    resource_type_str = interaction.resource_type.get_resource_type()

    return {
        "path": f"/{resource_type_str}/{{id}}",
        "response_model": interaction.resource_type,
        "status_code": status.HTTP_200_OK,
        "tags": [f"Type:{interaction.resource_type.get_resource_type()}"],
        "summary": f"{resource_type_str} {interaction.label()}",
        "description": f"The {resource_type_str} read interaction accesses "
        f"the current contents of a {resource_type_str} resource.",
        "responses": _responses(interaction, _ok, _unauthorized, _not_found),
        "response_model_exclude_none": True,
        **interaction.route_options,
    }


def search_type_route_args(
    interaction: TypeInteraction[ResourceType], post: bool
) -> dict[str, Any]:
    """Provide arguments for creation of a FHIR search-type API route."""
    resource_type_str = interaction.resource_type.get_resource_type()

    return {
        "path": f"/{resource_type_str}{'/_search' if post else ''}",
        "response_model": Bundle,
        "status_code": status.HTTP_200_OK,
        "tags": [f"Type:{interaction.resource_type.get_resource_type()}"],
        "summary": f"{resource_type_str} {interaction.label()}",
        "description": f"The {resource_type_str} search-type interaction searches a set of "
        "resources based on some filter criteria.",
        "responses": _responses(interaction, _ok, _bad_request, _unauthorized),
        "response_model_exclude_none": True,
        **interaction.route_options,
    }


def update_route_args(interaction: TypeInteraction[ResourceType]) -> dict[str, Any]:
    """Provide arguments for creation of a FHIR update API route."""
    resource_type_str = interaction.resource_type.get_resource_type()

    return {
        "path": f"/{resource_type_str}/{{id}}",
        "response_model": interaction.resource_type,
        "status_code": status.HTTP_200_OK,
        "tags": [f"Type:{interaction.resource_type.get_resource_type()}"],
        "summary": f"{resource_type_str} {interaction.label()}",
        "description": f"The {resource_type_str} update interaction creates a new current version "
        f"for an existing {resource_type_str} resource.",
        "responses": _responses(
            interaction, _ok, _bad_request, _unauthorized, _unprocessable_entity
        ),
        "response_model_exclude_none": True,
        **interaction.route_options,
    }


_Responses = dict[int, dict[str, Any]]


def _responses(
    interaction: TypeInteraction[ResourceType],
    *responses: Callable[[TypeInteraction[ResourceType]], _Responses],
) -> _Responses:
    """Combine the responses documentation for a FHIR interaction into a single dictionary."""
    merged_responses: _Responses = {}
    for response in responses:
        merged_responses |= response(interaction)
    return merged_responses


def _ok(interaction: TypeInteraction[ResourceType]) -> _Responses:
    """Return documentation for an HTTP 200 OK response."""
    return {
        status.HTTP_200_OK: {
            "model": interaction.resource_type
            if not isinstance(interaction, SearchTypeInteraction)
            else Bundle,
            "description": f"Successful {interaction.resource_type.get_resource_type()} "
            f"{interaction.label()}",
        }
    }


def _created(interaction: TypeInteraction[ResourceType]) -> _Responses:
    """Documentation for an HTTP 201 Created response."""
    return {
        status.HTTP_201_CREATED: {
            "model": interaction.resource_type,
            "description": f"Successful {interaction.resource_type.get_resource_type()} create",
        }
    }


def _bad_request(interaction: TypeInteraction[ResourceType]) -> _Responses:
    """Documentation for an HTTP 400 Bad Request response."""
    return {
        status.HTTP_400_BAD_REQUEST: {
            "model": OperationOutcome,
            "description": f"{interaction.resource_type.get_resource_type()} "
            f"{interaction.label()} request could not be parsed or "
            "failed basic FHIR validation rules.",
        }
    }


def _unauthorized(interaction: TypeInteraction[ResourceType]) -> _Responses:
    """Documentation for an HTTP 401 Unauthorized response."""
    return {
        status.HTTP_401_UNAUTHORIZED: {
            "model": OperationOutcome,
            "description": f"{interaction.resource_type.get_resource_type()} "
            f"Authorization is required for the {interaction.label()} interaction that was "
            "attempted.",
        }
    }


def _not_found(interaction: TypeInteraction[ResourceType]) -> _Responses:
    """Documentation for an HTTP 404 Not Found response."""
    return {
        status.HTTP_404_NOT_FOUND: {
            "model": OperationOutcome,
            "description": f"Unknown {interaction.resource_type.get_resource_type()} resource",
        }
    }


def _unprocessable_entity(interaction: TypeInteraction[ResourceType]) -> _Responses:
    """Documentation for an HTTP 422 Unprocessable Entity response."""
    return {
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": OperationOutcome,
            "description": f"The proposed {interaction.resource_type.get_resource_type()} resource"
            " violated applicable "
            "FHIR profiles or server business rules.",
        }
    }
