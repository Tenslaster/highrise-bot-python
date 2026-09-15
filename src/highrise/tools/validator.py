from typing import Any, Iterable, Type, Pattern

from highrise.constants import FACING_DIRECTIONS

class Validator:
    """Chainable input validator for SDK-wide argument checking.

    Every method raises ValueError on failure and returns self,
    so calls can be chained together in a single expression.
    """

    @staticmethod
    def string(value: Any, field: str) -> "Validator":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return Validator

    @staticmethod
    def number(value: Any, field: str) -> "Validator":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a number")
        return Validator

    @staticmethod
    def callable(value: Any, field: str) -> "Validator":
        if not callable(value):
            raise ValueError(f"{field} must be callable")
        return Validator

    @staticmethod
    def required(value: Any, field: str) -> "Validator":
        if value is None:
            raise ValueError(f"{field} is required")
        return Validator

    @staticmethod
    def range(value: Any, minimum: float, maximum: float, field: str) -> "Validator":
        if value < minimum or value > maximum:
            raise ValueError(f"{field} must be between {minimum} and {maximum}")
        return Validator

    @staticmethod
    def one_of(value: Any, options: Iterable[Any], field: str) -> "Validator":
        if value not in options:
            raise ValueError(f"{field} must be one of: {', '.join(map(str, options))}")
        return Validator

    @staticmethod
    def boolean(value: Any, field: str) -> "Validator":
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be a boolean")
        return Validator

    @staticmethod
    def array(value: Any, field: str) -> "Validator":
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{field} must be an array")
        return Validator
    
    @staticmethod
    def non_empty_array(value: Any, field: str) -> "Validator":
        if not isinstance(value, (list, tuple)) or len(value) == 0:
            raise ValueError(f"{field} must be a non-empty array")
        return Validator
    
    @staticmethod
    def min_length(value: Any, minimum: int, field: str) -> "Validator":
        if not isinstance(value, str) or len(value) < minimum:
            raise ValueError(f"{field} must be at least {minimum} characters")
        return Validator
    
    @staticmethod
    def max_items(value: Any, maximum: int, field: str) -> "Validator":
        if not isinstance(value, list) or len(value) > maximum:
            raise ValueError(f"{field} must have at most {maximum} items")
        return Validator
    
    @staticmethod
    def max_length(value: Any, maximum: int, field: str) -> "Validator":
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError(f"{field} must be at most {maximum} characters")
        return Validator
    
    @staticmethod
    def integer(value: Any, field: str) -> "Validator":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{field} must be an integer")
        return Validator
    
    @staticmethod
    def positive(value: Any, field: str) -> "Validator":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"{field} must be a positive number")
        return Validator
    
    @staticmethod
    def non_negative(value: Any, field: str) -> "Validator":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{field} must be 0 or greater")
        return Validator
    
    @staticmethod
    def instance_of(value: Any, expected_type: Type, field: str) -> "Validator":
        if not isinstance(value, expected_type):
            raise ValueError(f"{field} must be an instance of {expected_type.__name__}")
        return Validator
    
    @staticmethod
    def match(value: Any, pattern: Pattern, field: str) -> "Validator":
        if not isinstance(value, str) or not pattern.search(value):
            raise ValueError(f"{field} does not match the required pattern")
        return Validator
    
    @staticmethod
    def object(value: Any, field: str) -> "Validator":
        if not isinstance(value, dict):
            raise ValueError(f"{field} must be a plain object")
        return Validator
    
    @staticmethod
    def is_coordinates(x: Any, y: Any, z: Any, facing: Any) -> "Validator":
        (
            Validator.required(x, "x").non_negative(x, "x")
            .required(y, "y").number(y, "y")
            .required(z, "z").non_negative(z, "z")
            .required(facing, "facing")
            .string(facing, "facing")
            .one_of(facing, FACING_DIRECTIONS, "facing")
        )
        return Validator
    
    @staticmethod
    def is_anchor(entity_id: Any, anchor_ix: Any) -> "Validator":
        (
            Validator.required(entity_id, "entity_id").string(entity_id, "entity_id")
            .required(anchor_ix, "anchor_ix").non_negative(anchor_ix, "anchor_ix")
        )
        return Validator