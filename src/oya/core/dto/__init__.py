from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from typing import Any, Generator, Generic, Optional, TypeVar

from msgspec import Meta
from typing_extensions import Annotated

from litestar.dto import AbstractDTO, DTOField, Mark
from litestar.dto.data_structures import DTOFieldDefinition
from litestar.exceptions import MissingDependencyException
from litestar.types import Empty
from litestar.typing import FieldDefinition

try:
    import tortoise # noqa: F401
except ImportError as e:
    raise MissingDependencyException("tortoise") from e


from tortoise.fields import Field
from tortoise import fields
from tortoise.models import Model


from oya.apps import apps


T = TypeVar("T", bound=Model)

__all__ = ["TortoiseDTO"]


def _parse_toirtoise_type(field: Field, extra: dict[str, Any]) -> FieldDefinition:
    if isinstance(field, (tortoise.fields.relational.ForeignKeyFieldInstance,)):
        _app, model_name = field.model_name.split('.')
        related_model = apps.get_model(app_label=_app, model_name=model_name)
        field_type = related_model
        meta = Meta(extra=extra)

    elif isinstance(field, (fields.IntField, fields.SmallIntField)):
        field_type = int
        meta = Meta(extra=extra)

    elif isinstance(field, (fields.BigIntField, fields.FloatField)):
        field_type: Any = Decimal
        meta = Meta(extra=extra)

    elif isinstance(field, (fields.CharField,)):
        field_type = str
        meta = Meta(max_length=field.max_length, extra=extra)

    elif isinstance(field, (fields.JSONField,)):
        field_type = str
        meta = Meta(extra={**extra, "format": "json"})

    elif isinstance(field, (fields.TextField,)):
        field_type = str
        meta = Meta(extra={**extra, "format" : "text-area"})

    else:
        field_type = field.field_type
        meta = Meta(extra=extra)
    
    if not field.required:
        field_type = Optional[field_type]

    return  FieldDefinition.from_annotation(Annotated[field_type, meta])

def _create_field_extra(field: Field) -> dict[str, Any]:
    extra : dict[str, Any] = {}
    if field.description:
        extra["description"] = field.description

    if hasattr(field, 'enum_type'):
        extra["enum"] = list(field.enum_type)

    return extra


class TortoiseDTO(AbstractDTO[T], Generic[T]):
    
    @classmethod
    def generate_field_definitions(cls, model_type: type[Model]) -> Generator[FieldDefinition, None, None]:
        
        for field in model_type._meta.fields_map.values():
            
            yield replace(
                DTOFieldDefinition.from_field_definition(
                    field_definition=_parse_toirtoise_type(field, _create_field_extra(field)),
                    dto_field=DTOField(mark=Mark.READ_ONLY if field.pk else None),
                    model_name=model_type.__name__,
                    default_factory=lambda x: x,  # i don't know why Empty  doesn't work, but it works for PiccoloDTO
                ),
                default=Empty if field.required else None,
                name=field.model_field_name,
            )

    @classmethod
    def detect_nested_field(cls, field_definition: FieldDefinition) -> bool:
        return field_definition.is_subclass_of(Model)
