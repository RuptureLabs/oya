from typing import TYPE_CHECKING, Any
import re
from tortoise import fields
from tortoise.exceptions import ConfigurationError, ValidationError
from tortoise.validators import RegexValidator, MaxLengthValidator

if TYPE_CHECKING:
    from tortoise.fields import Field


class EMailValidator(RegexValidator):
    """Rewrite the regex validator to support email address validation, only for clean error message"""

    def __call__(self, value: Any):
        if not self.regex.match(value):
            raise ValidationError(f"Value '{value}' is not a valid email address")


class EmailField(fields.CharField):
    field_type = str
    pattern = "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(max_length = 255, **kwargs)
        self.validators.append(EMailValidator(self.pattern, re.I))

    @property
    def constraints(self) -> dict:
        return {
            "pattern": self.pattern,
            "max_length": self.max_length,
        }


class JSONBField(fields.JSONField):
    pass