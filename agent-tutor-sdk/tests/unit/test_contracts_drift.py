"""Строгие тесты drift между Pydantic (contracts) и JSON Schema (data-service).

Source of truth: Go models в data-service/internal/models/models.go.
JSON Schema в specs/schemas/*.schema.json генерируется из Go (cmd/schema-gen).
Pydantic в agent_tutor_sdk.contracts должен точно соответствовать этим схемам:
- имена полей (с учётом alias)
- описания полей (description)
- обязательность (required vs Optional + default)

Если тесты падают — кто-то поменял Go-модель или Pydantic вручную
и забыл синхронизировать.

Запуск:
    uv run pytest agent-tutor-sdk/tests/unit/test_contracts_drift.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from agent_tutor_sdk.contracts import (
    Discipline,
    Grade,
    Group,
    Lesson,
    ScheduleEntry,
    Student,
    Teacher,
)

SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "specs" / "schemas"


def _load_schema(name: str) -> dict[str, Any]:
    """Загрузить JSON Schema по имени модели (PascalCase)."""
    # ScheduleEntry → schedule-entry, остальные просто lowercase
    stem = "schedule-entry" if name == "ScheduleEntry" else name.lower()
    path = SCHEMAS_DIR / f"{stem}.schema.json"
    if not path.exists():
        pytest.fail(f"JSON Schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _pydantic_fields(model: type[BaseModel]) -> dict[str, dict[str, Any]]:
    """Извлечь инфо о полях Pydantic-модели.

    Возвращает: {resolve_name: {alias, description, required, type}}
    resolve_name — это либо alias (если задан), либо имя поля.
    """
    result = {}
    for name, field in model.model_fields.items():
        # FieldInfo.alias может быть None или str
        alias = field.alias or name
        # description
        desc = field.description
        # required: нет default И нет default_factory
        required = field.is_required()
        result[alias] = {
            "pyd_name": name,
            "description": desc,
            "required": required,
        }
    return result


# === Карта моделей для параметризации ===

MODELS = [
    (Group, "Group"),
    (Student, "Student"),
    (Teacher, "Teacher"),
    (Discipline, "Discipline"),
    (Grade, "Grade"),
    (Lesson, "Lesson"),
    (ScheduleEntry, "ScheduleEntry"),
]


# === Тесты: имена полей ===

@pytest.mark.parametrize("model_cls,schema_name", MODELS, ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_schema_file_exists(model_cls, schema_name):
    """JSON Schema файл для модели существует."""
    _load_schema(schema_name)


@pytest.mark.parametrize("model_cls,schema_name", MODELS, ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_field_names_match_schema(model_cls, schema_name):
    """Каждое поле Pydantic (или его alias) присутствует в JSON Schema.

    Не должно быть лишних полей в Pydantic, отсутствующих в схеме.
    Не должно быть полей в схеме, не покрытых Pydantic.
    """
    schema = _load_schema(schema_name)
    schema_fields = set(schema.get("properties", {}).keys())
    pyd_fields = set(_pydantic_fields(model_cls).keys())

    extra_in_pyd = pyd_fields - schema_fields
    missing_in_pyd = schema_fields - pyd_fields

    assert not extra_in_pyd, (
        f"{model_cls.__name__}: Pydantic has fields not in JSON Schema: {sorted(extra_in_pyd)}"
    )
    assert not missing_in_pyd, (
        f"{model_cls.__name__}: JSON Schema has fields not in Pydantic: {sorted(missing_in_pyd)}"
    )


# === Тесты: описания полей ===

@pytest.mark.parametrize("model_cls,schema_name", MODELS, ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_field_descriptions_match_schema(model_cls, schema_name):
    """description каждого поля Pydantic точно совпадает с JSON Schema."""
    schema = _load_schema(schema_name)
    schema_props = schema.get("properties", {})
    pyd_fields = _pydantic_fields(model_cls)

    mismatches = []
    for field_name, pyd_info in pyd_fields.items():
        if field_name not in schema_props:
            continue  # уже проверяется в test_field_names_match_schema
        schema_desc = schema_props[field_name].get("description", "")
        pyd_desc = pyd_info["description"]
        if schema_desc != pyd_desc:
            mismatches.append({
                "field": field_name,
                "schema": schema_desc,
                "pydantic": pyd_desc,
            })

    assert not mismatches, (
        f"{model_cls.__name__}: description drift in fields:\n"
        + "\n".join(
            f"  - {m['field']}:\n"
            f"      schema:   {m['schema']!r}\n"
            f"      pydantic: {m['pydantic']!r}"
            for m in mismatches
        )
    )


# === Тесты: required vs optional ===

@pytest.mark.parametrize("model_cls,schema_name", MODELS, ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_required_fields_match_schema(model_cls, schema_name):
    """Поля в JSON Schema required[] должны быть required в Pydantic (без default).

    NB: Pydantic считает поле required если нет default и нет default_factory.
    Сейчас JSON Schema в проекте НЕ использует "required" массив (все поля optional
    на уровне схемы). Поэтому проверка работает в одну сторону: Pydantic required →
    должен быть в схеме, но обратное не проверяем.
    """
    schema = _load_schema(schema_name)
    schema_required = set(schema.get("required", []))
    pyd_fields = _pydantic_fields(model_cls)

    # Если схема говорит required, Pydantic должен тоже
    for req_field in schema_required:
        # ищем либо по alias, либо по pyd_name
        pyd_info = pyd_fields.get(req_field)
        if pyd_info is None:
            # может быть по pyd_name
            for fi in pyd_fields.values():
                if fi["pyd_name"] == req_field:
                    pyd_info = fi
                    break
        if pyd_info is None:
            pytest.fail(
                f"{model_cls.__name__}: required field {req_field!r} from schema "
                f"not found in Pydantic"
            )
        assert pyd_info["required"], (
            f"{model_cls.__name__}: field {req_field!r} is required in schema "
            f"but has default in Pydantic"
        )


# === Тесты: round-trip парсинг из реального формата JSON Schema ===

@pytest.mark.parametrize("model_cls,schema_name", MODELS, ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_model_parses_minimal_schema_payload(model_cls, schema_name):
    """Pydantic может распарсить полный JSON-payload со всеми полями из схемы.

    Берёт каждый field из schema.properties и даёт dummy-значение нужного типа.
    Это имитирует реальный HTTP-ответ от data-service (все поля есть).
    """
    schema = _load_schema(schema_name)
    props = schema.get("properties", {})

    # Собираем полный payload: каждое поле из схемы получает dummy-значение
    payload = {}
    for fname, prop in props.items():
        # nested object — для теста достаточно {}
        # Но если у объекта есть properties (инлайн-схема вложенного типа),
        # передаём nested payload
        nested_props = prop.get("properties")
        if nested_props:
            nested_payload = {}
            for nname, nprop in nested_props.items():
                ntype = nprop.get("type")
                if isinstance(ntype, list):
                    ntype = next((t for t in ntype if t != "null"), "string")
                if ntype == "integer":
                    nested_payload[nname] = 1
                else:
                    nested_payload[nname] = "x"
            payload[fname] = nested_payload
            continue

        # array — пустой массив или массив с одним элементом
        if prop.get("type") == "array":
            items_schema = prop.get("items", {})
            if items_schema.get("type") == "object":
                # пустой массив ок для начала
                payload[fname] = []
            elif items_schema.get("type") == "integer":
                payload[fname] = [1]
            else:
                payload[fname] = ["x"]
            continue

        prop_type = prop.get("type")
        if isinstance(prop_type, list):
            prop_type = next((t for t in prop_type if t != "null"), "string")
        if prop_type == "integer":
            payload[fname] = 1
        elif prop_type == "number":
            payload[fname] = 1.0
        elif prop_type == "boolean":
            payload[fname] = False
        else:
            payload[fname] = "x"

    # Проверяем что модель принимает полный payload
    instance = model_cls(**payload)
    assert instance is not None


@pytest.mark.parametrize("model_cls,schema_name", MODELS, ids=lambda v: v if isinstance(v, str) else v.__name__)
def test_model_rejects_unknown_fields(model_cls, schema_name):
    """Pydantic отвергает unknown поля (additionalProperties=false в схеме).

    По умолчанию Pydantic v2 разрешает extras — нужно либо model_config = extra='forbid',
    либо проверить что отсутствие запрета — осознанный выбор.
    Этот тест проверяет, что поведение Pydantic совпадает со схемой.
    Если схема говорит additionalProperties: false, Pydantic должен тоже запрещать.
    """
    schema = _load_schema(schema_name)
    if schema.get("additionalProperties") is not False:
        pytest.skip(f"{model_cls.__name__}: schema allows additionalProperties")

    # Если в схеме запрещены extras — Pydantic должен быть настроен соответственно
    extra_setting = model_cls.model_config.get("extra")
    assert extra_setting == "forbid", (
        f"{model_cls.__name__}: schema forbids additionalProperties=false, "
        f"but Pydantic model_config.extra={extra_setting!r} (expected 'forbid')"
    )


# === Тест: каждая модель доступна через `from agent_tutor_sdk.contracts` ===

def test_all_models_exported():
    """Все ожидаемые модели экспортируются из contracts."""
    from agent_tutor_sdk import contracts
    expected = {"Group", "Student", "Teacher", "Discipline", "Grade", "Lesson", "ScheduleEntry"}
    actual = {name for name in dir(contracts) if isinstance(getattr(contracts, name), type) and issubclass(getattr(contracts, name), BaseModel)}
    missing = expected - actual
    assert not missing, f"Missing exports: {missing}"