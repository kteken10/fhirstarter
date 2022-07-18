"""Classes and types for handling and representing FHIR Interactions."""

from abc import abstractmethod
from typing import Any, Generic, Literal, Protocol, TypeVar

from fastapi import Request, Response
from fhir.resources.bundle import Bundle
from fhir.resources.fhirtypes import Id
from fhir.resources.resource import Resource

ResourceType = TypeVar("ResourceType", bound=Resource)


# TODO: Revisit definition of callback protocols and see if it is possible to make Mypy like them
class CreateInteractionCallable(Protocol[ResourceType]):  # type: ignore
    """Callback protocol that defines the signature of a callable for a FHIR create interaction."""

    async def __call__(
        self, resource: ResourceType, *, request: Request, response: Response
    ) -> Id | ResourceType:
        ...


class ReadInteractionCallable(Protocol[ResourceType]):  # type: ignore
    """Callback protocol that defines the signature of a callable for a FHIR read interaction."""

    async def __call__(
        self, id_: Id, *, request: Request, response: Response
    ) -> ResourceType:
        ...


class SearchTypeInteractionCallable(Protocol):
    """
    Callback protocol that defines the signature of a callable for a FHIR search-type interaction.
    """

    async def __call__(
        self, *, request: Request, response: Response, **kwargs: Any
    ) -> Bundle:
        ...


class UpdateInteractionCallable(Protocol[ResourceType]):  # type: ignore
    """Callback protocol that defines the signature of a callable for a FHIR update interaction."""

    async def __call__(
        self, id_: Id, resource: ResourceType, *, request: Request, response: Response
    ) -> Id | ResourceType:
        ...


InteractionCallable = (
    CreateInteractionCallable[ResourceType]
    | ReadInteractionCallable[ResourceType]
    | SearchTypeInteractionCallable
    | UpdateInteractionCallable[ResourceType]
)


class TypeInteraction(Generic[ResourceType]):
    """
    Collection of values that represent a FHIR type interactions. This class can also represent
    instance level interactions.

    resource_type:    The type of FHIR resource on which this interaction operates, as defined by
                      the fhir.resources package.
    callable_:        User-defined function that performs the FHIR interaction.
    route_options:    Dictionary of key-value pairs that are passed on to FastAPI on route creation.
    """

    def __init__(
        self,
        resource_type: type[ResourceType],
        callable_: InteractionCallable[ResourceType],
        route_options: dict[str, Any],
    ):
        self.resource_type = resource_type
        self.callable_ = callable_
        self.route_options = route_options

    @staticmethod
    @abstractmethod
    def label() -> str:
        raise NotImplementedError


class CreateInteraction(TypeInteraction[ResourceType]):
    @staticmethod
    def label() -> Literal["create"]:
        return "create"


class ReadInteraction(TypeInteraction[ResourceType]):
    @staticmethod
    def label() -> Literal["read"]:
        return "read"


class SearchTypeInteraction(TypeInteraction[ResourceType]):
    @staticmethod
    def label() -> Literal["search-type"]:
        return "search-type"


class UpdateInteraction(TypeInteraction[ResourceType]):
    @staticmethod
    def label() -> Literal["update"]:
        return "update"
