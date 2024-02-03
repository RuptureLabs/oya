from __future__ import annotations
from typing import TYPE_CHECKING, Any
from litestar.dto import AbstractDTO

from litestar.plugins import SerializationPluginProtocol
from litestar.typing import FieldDefinition
from oya.core.dto import TortoiseDTO
from tortoise.models import Model


__all__ = ["TortoiseSerializationPlugin"]

if TYPE_CHECKING:
    from litestar.typing import FieldDefinition

class TortoiseSerializationPlugin(SerializationPluginProtocol):
    __slots__ = ("_type_dto_map", "_config")
    def __init__(self) -> None:
        super().__init__()
        self._type_dto_map: dict[type[Model], TortoiseDTO[Any]] = {}
        
    def supports_type(self, field_definition: FieldDefinition) -> bool:
        return (field_definition.is_collection and field_definition.has_inner_subclass_of(Model)
        ) or field_definition.is_subclass_of(Model)
        
    
    def create_dto_for_type(self, field_definition: FieldDefinition) -> type[AbstractDTO]:
        annotation = next(
            (
                inner_type.annotation
                for inner_type in field_definition.inner_types
                if inner_type.is_subclass_of(Model)
            ),
            field_definition.annotation,
        )

        if annotation in self._type_dto_map:
            return self._type_dto_map[annotation]
        
        self._type_dto_map[annotation] = dto_type = TortoiseDTO[annotation]

        return dto_type
