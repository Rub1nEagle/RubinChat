"""Перевод pydantic-ошибок валидации на русский.

FastAPI на 422 отдаёт массив `detail`, в котором каждый элемент имеет
вид ``{"type": "...", "loc": [...], "msg": "...", "input": ..., "ctx": ...}``.
Стандартные `msg` — на английском («Field required», «String should have
at least N characters» и т. д.). Мы оставляем структуру `loc/type`, но
заменяем `msg` русским эквивалентом, так чтобы клиент мог показывать
их пользователю как есть.
"""
from __future__ import annotations

from typing import Any

# Русские названия для часто встречающихся в схемах полей. Если поля
# нет — берём последний элемент `loc` как есть.
_FIELD_RU: dict[str, str] = {
    "username": "имя пользователя",
    "password": "пароль",
    "current_password": "текущий пароль",
    "new_password": "новый пароль",
    "plaintext": "текст сообщения",
    "encrypted_payload_hex": "шифртекст",
    "nonce_hex": "nonce",
    "signature_hex": "подпись",
    "sender_private_key_hex": "приватный ключ",
    "recipient_id": "получатель",
    "sender_id": "отправитель",
    "peer_id": "собеседник",
    "attachment_id": "вложение",
    "before_id": "курсор",
    "limit": "лимит",
    "display_name": "отображаемое имя",
    "bio": "описание",
    "items": "список",
    "file": "файл",
}


def _field_label(loc: tuple[Any, ...]) -> str:
    if not loc:
        return "поле"
    last = str(loc[-1])
    return _FIELD_RU.get(last, last)


def _translate_one(err: dict[str, Any]) -> dict[str, Any]:
    etype = err.get("type", "")
    ctx = err.get("ctx") or {}
    loc = tuple(err.get("loc") or ())
    field = _field_label(loc)

    # Самые ходовые типы pydantic v2 — переводим адресно.
    if etype == "missing":
        msg = f"Не заполнено: {field}"
    elif etype == "string_too_short":
        n = ctx.get("min_length")
        msg = f"{field.capitalize()}: минимум {n} символ(ов)" if n else f"{field.capitalize()}: слишком короткое значение"
    elif etype == "string_too_long":
        n = ctx.get("max_length")
        msg = f"{field.capitalize()}: максимум {n} символ(ов)" if n else f"{field.capitalize()}: слишком длинное значение"
    elif etype == "string_pattern_mismatch":
        msg = f"{field.capitalize()}: недопустимые символы"
    elif etype in ("int_parsing", "int_type"):
        msg = f"{field.capitalize()}: ожидается целое число"
    elif etype in ("float_parsing", "float_type"):
        msg = f"{field.capitalize()}: ожидается число"
    elif etype in ("bool_parsing", "bool_type"):
        msg = f"{field.capitalize()}: ожидается true/false"
    elif etype in ("greater_than", "greater_than_equal"):
        bound = ctx.get("ge", ctx.get("gt"))
        msg = f"{field.capitalize()}: значение должно быть не меньше {bound}" if bound is not None else f"{field.capitalize()}: значение слишком маленькое"
    elif etype in ("less_than", "less_than_equal"):
        bound = ctx.get("le", ctx.get("lt"))
        msg = f"{field.capitalize()}: значение должно быть не больше {bound}" if bound is not None else f"{field.capitalize()}: значение слишком большое"
    elif etype == "value_error":
        # Pydantic пускает сюда ValueError из @validator'ов. Текст ошибки
        # уже может быть на русском (наш собственный raise) — оставим как есть,
        # но без префикса «Value error,».
        raw = err.get("msg", "")
        if raw.startswith("Value error, "):
            raw = raw[len("Value error, "):]
        msg = raw or f"{field.capitalize()}: некорректное значение"
    elif etype == "json_invalid":
        msg = "Тело запроса не является корректным JSON"
    elif etype == "list_type":
        msg = f"{field.capitalize()}: ожидается список"
    elif etype == "too_long":
        n = ctx.get("max_length")
        msg = f"{field.capitalize()}: больше {n} элементов" if n else f"{field.capitalize()}: слишком много элементов"
    elif etype == "too_short":
        n = ctx.get("min_length")
        msg = f"{field.capitalize()}: меньше {n} элементов" if n else f"{field.capitalize()}: слишком мало элементов"
    elif etype == "literal_error":
        expected = ctx.get("expected", "")
        msg = f"{field.capitalize()}: допустимые значения — {expected}"
    elif etype == "extra_forbidden":
        msg = f"Лишнее поле: {field}"
    else:
        # Фолбэк — английская форма из pydantic. Лучше показать что-то,
        # чем потерять диагностику; UI всё равно покажет {field}: ...
        msg = err.get("msg") or "некорректное значение"

    return {**err, "msg": msg}


def translate_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_translate_one(e) for e in errors]
