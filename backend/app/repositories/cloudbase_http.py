"""CloudBase PostgreSQL HTTP API adapter.

The shared free PG cluster does not expose the PostgreSQL wire protocol. This
adapter presents the narrow SQLAlchemy Session surface already consumed by the
application while translating simple CRUD to PostgREST and explicit atomic
operations to PostgreSQL functions under ``/rpc``.
"""

from __future__ import annotations

from copy import deepcopy
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any

import httpx
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.sql import operators
from sqlalchemy.sql.dml import Delete, Update
from sqlalchemy.sql.elements import (
    BindParameter,
    BooleanClauseList,
    False_,
    Null,
    True_,
    UnaryExpression,
)
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.selectable import Select
from sqlalchemy.sql.sqltypes import DateTime

from ..config import Settings


class CloudBaseDataError(RuntimeError):
    """A sanitized CloudBase Data API failure safe to record in server logs."""

    def __init__(self, operation: str, status_code: int, detail: str):
        super().__init__(f"CloudBase data {operation} failed ({status_code}): {detail}")
        self.operation = operation
        self.status_code = status_code


@dataclass
class MutationResult:
    rowcount: int


class _Query:
    def __init__(self, session: "CloudBaseHttpSession", model: type[Any]):
        self.session = session
        self.model = model
        self.criteria: list[Any] = []

    def filter(self, *criteria: Any) -> "_Query":
        self.criteria.extend(criteria)
        return self

    def first(self) -> Any | None:
        rows = self.session._select_model(self.model, self.criteria, limit=1)
        return rows[0] if rows else None

    def one_or_none(self) -> Any | None:
        rows = self.session._select_model(self.model, self.criteria, limit=2)
        if len(rows) > 1:
            raise RuntimeError("query returned more than one row")
        return rows[0] if rows else None


class CloudBaseHttpSession:
    """HTTP-backed repository with a Session-compatible unit-of-work surface."""

    is_cloudbase_http = True

    def __init__(
        self,
        *,
        env_id: str,
        api_key: str,
        api_url: str = "",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.env_id = env_id.strip()
        self.api_url = (
            api_url.strip().rstrip("/")
            or f"https://{self.env_id}.api.tcloudbasegateway.com/v1/rdb/rest"
        )
        self._client = httpx.Client(
            base_url=self.api_url + "/",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            transport=transport,
            trust_env=False,
        )
        self._pending_adds: list[Any] = []
        self._pending_deletes: list[Any] = []
        self._tracked: dict[int, tuple[Any, dict[str, Any]]] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> "CloudBaseHttpSession":
        return cls(
            env_id=settings.cloudbase_env_id,
            api_key=settings.cloudbase_api_key,
            api_url=settings.cloudbase_pg_api_url,
            timeout=settings.cloudbase_http_timeout_seconds,
        )

    def __enter__(self) -> "CloudBaseHttpSession":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def healthcheck(self) -> None:
        self._request("GET", "users", params=[("select", "id"), ("limit", "1")])

    def rpc(self, function_name: str, parameters: dict[str, Any]) -> Any:
        response = self._request(
            "POST", f"rpc/{function_name}", json=self._json_value(parameters)
        )
        return response.json() if response.content else None

    def query(self, model: type[Any]) -> _Query:
        return _Query(self, model)

    def get(self, model: type[Any], primary_key: Any) -> Any | None:
        mapper = sa_inspect(model)
        primary_keys = list(mapper.primary_key)
        if len(primary_keys) != 1:
            raise NotImplementedError("CloudBase adapter requires a single-column key")
        rows = self._select_model(model, [primary_keys[0] == primary_key], limit=1)
        return rows[0] if rows else None

    def scalars(self, statement: Select) -> list[Any]:
        return self._select(statement)

    def scalar(self, statement: Select) -> Any:
        rows = self._select(statement)
        return rows[0] if rows else None

    def add(self, instance: Any) -> None:
        self._pending_adds.append(instance)

    def add_all(self, instances: list[Any]) -> None:
        self._pending_adds.extend(instances)

    def delete(self, instance: Any) -> None:
        self._pending_deletes.append(instance)

    def expire_all(self) -> None:
        # HTTP reads are never backed by a local identity map cache.
        return None

    def rollback(self) -> None:
        self._pending_adds.clear()
        self._pending_deletes.clear()

    def refresh(self, instance: Any) -> None:
        mapper = sa_inspect(type(instance))
        pk = mapper.primary_key[0]
        fresh = self.get(type(instance), getattr(instance, pk.key))
        if fresh is None:
            raise CloudBaseDataError("refresh", 404, "row not found")
        self._copy_columns(fresh, instance)
        self._track(instance)

    def commit(self) -> None:
        self._flush_adds()
        self._flush_dirty()
        self._flush_deletes()

    def execute(self, statement: Any) -> MutationResult:
        if isinstance(statement, Update):
            values = {
                column.key: self._bound_value(value)
                for column, value in statement._values.items()
            }
            return self._patch(statement.table.name, statement._where_criteria, values)
        if isinstance(statement, Delete):
            return self._delete_where(statement.table.name, statement._where_criteria)
        raise NotImplementedError(
            f"CloudBase adapter cannot execute {type(statement).__name__}"
        )

    def _select_model(
        self, model: type[Any], criteria: list[Any], limit: int | None = None
    ) -> list[Any]:
        params = [("select", "*")]
        params.extend(self._criteria_params(criteria))
        if limit is not None:
            params.append(("limit", str(limit)))
        response = self._request("GET", model.__tablename__, params=params)
        rows = response.json()
        return [self._hydrate(model, row) for row in rows]

    def _select(self, statement: Select) -> list[Any]:
        descriptions = statement.column_descriptions
        expression = descriptions[0]["expr"]
        entity = descriptions[0].get("entity")
        from_table = statement.get_final_froms()[0]
        params: list[tuple[str, str]] = []

        if isinstance(expression, count):
            params.extend(self._criteria_params(list(statement._where_criteria)))
            response = self._request(
                "HEAD",
                from_table.name,
                params=params,
                headers={"Prefer": "count=exact"},
            )
            content_range = response.headers.get("content-range", "*/0")
            return [int(content_range.rsplit("/", 1)[-1])]

        returns_model = isinstance(expression, type) and entity is expression
        selected_name = "*" if returns_model else descriptions[0]["name"]
        params.append(("select", selected_name))
        params.extend(self._criteria_params(list(statement._where_criteria)))
        if statement._order_by_clauses:
            params.append(
                (
                    "order",
                    ",".join(
                        self._compile_order(item)
                        for item in statement._order_by_clauses
                    ),
                )
            )
        if statement._limit_clause is not None:
            params.append(("limit", str(statement._limit_clause.value)))
        response = self._request("GET", from_table.name, params=params)
        rows = response.json()
        if returns_model:
            return [self._hydrate(entity, row) for row in rows]
        return [row.get(selected_name) for row in rows]

    def _flush_adds(self) -> None:
        grouped: defaultdict[type[Any], list[Any]] = defaultdict(list)
        for instance in self._pending_adds:
            grouped[type(instance)].append(instance)
        self._pending_adds.clear()
        for model, instances in grouped.items():
            payloads = [
                self._instance_payload(instance, for_insert=True)
                for instance in instances
            ]
            body: Any = payloads[0] if len(payloads) == 1 else payloads
            response = self._request(
                "POST",
                model.__tablename__,
                json=body,
                headers={"Prefer": "return=representation"},
            )
            returned = response.json()
            if isinstance(returned, dict):
                returned = [returned]
            mapper = sa_inspect(model)
            pk_name = mapper.primary_key[0].key
            by_pk = {row.get(pk_name): row for row in returned}
            for index, instance in enumerate(instances):
                row = by_pk.get(getattr(instance, pk_name, None))
                if row is None and index < len(returned):
                    row = returned[index]
                if row is not None:
                    self._copy_row(row, instance)
                self._track(instance)

    def _flush_dirty(self) -> None:
        for instance, snapshot in list(self._tracked.values()):
            if instance in self._pending_deletes:
                continue
            current = self._instance_payload(instance)
            changes = {
                key: value
                for key, value in current.items()
                if snapshot.get(key) != value
            }
            if not changes:
                continue
            mapper = sa_inspect(type(instance))
            pk = mapper.primary_key[0]
            if pk.key in changes:
                raise ValueError("primary key updates are not supported")
            for column in mapper.columns:
                if column.onupdate is not None:
                    value = self._evaluate_default(column.onupdate)
                    setattr(instance, column.key, value)
                    changes[column.key] = self._json_value(value)
            result = self._patch(
                type(instance).__tablename__,
                [pk == getattr(instance, pk.key)],
                changes,
            )
            if result.rowcount != 1:
                raise CloudBaseDataError("update", 409, "row changed or disappeared")
            self._track(instance)

    def _flush_deletes(self) -> None:
        pending = list(self._pending_deletes)
        self._pending_deletes.clear()
        for instance in pending:
            mapper = sa_inspect(type(instance))
            pk = mapper.primary_key[0]
            self._delete_where(
                type(instance).__tablename__, [pk == getattr(instance, pk.key)]
            )
            self._tracked.pop(id(instance), None)

    def _patch(
        self, table: str, criteria: Any, values: dict[str, Any]
    ) -> MutationResult:
        response = self._request(
            "PATCH",
            table,
            params=self._criteria_params(list(criteria)),
            json=self._json_value(values),
            headers={"Prefer": "return=representation"},
        )
        rows = response.json() if response.content else []
        return MutationResult(len(rows))

    def _delete_where(self, table: str, criteria: Any) -> MutationResult:
        response = self._request(
            "DELETE",
            table,
            params=self._criteria_params(list(criteria)),
            headers={"Prefer": "return=representation"},
        )
        rows = response.json() if response.content else []
        return MutationResult(len(rows))

    def _hydrate(self, model: type[Any], row: dict[str, Any]) -> Any:
        instance = model()
        self._copy_row(row, instance)
        self._track(instance)
        return instance

    @staticmethod
    def _copy_columns(source: Any, target: Any) -> None:
        for column in sa_inspect(type(target)).columns:
            setattr(target, column.key, getattr(source, column.key))

    def _copy_row(self, row: dict[str, Any], instance: Any) -> None:
        mapper = sa_inspect(type(instance))
        for column in mapper.columns:
            if column.key not in row:
                continue
            value = row[column.key]
            if (
                value is not None
                and isinstance(column.type, DateTime)
                and isinstance(value, str)
            ):
                value = self._parse_datetime(value)
            setattr(instance, column.key, value)

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """Accept PostgreSQL fractional seconds on Python 3.10.

        CloudBase can emit 1-6 fractional digits while Python 3.10's
        ``fromisoformat`` only accepts selected precisions. Normalize the
        fractional component to six digits without changing its value.
        """

        normalized = value.replace("Z", "+00:00")
        match = re.fullmatch(
            r"(.*[T ]\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})?",
            normalized,
        )
        if match:
            prefix, fraction, offset = match.groups()
            normalized = (
                f"{prefix}.{(fraction + '000000')[:6]}{offset or ''}"
            )
        return datetime.fromisoformat(normalized)

    def _track(self, instance: Any) -> None:
        self._tracked[id(instance)] = (
            instance,
            deepcopy(self._instance_payload(instance)),
        )

    def _instance_payload(
        self, instance: Any, *, for_insert: bool = False
    ) -> dict[str, Any]:
        mapper = sa_inspect(type(instance))
        payload: dict[str, Any] = {}
        explicit = instance.__dict__
        for column in mapper.columns:
            value = getattr(instance, column.key, None)
            if for_insert and value is None and column.default is not None:
                value = self._evaluate_default(column.default)
                setattr(instance, column.key, value)
            if (
                for_insert
                and value is None
                and column.primary_key
                and column.autoincrement is True
            ):
                continue
            if (
                for_insert
                and value is None
                and column.key not in explicit
                and column.nullable
            ):
                continue
            payload[column.key] = self._json_value(value)
        return payload

    @staticmethod
    def _evaluate_default(default: Any) -> Any:
        value = default.arg
        if callable(value):
            try:
                return value(None)
            except TypeError:
                return value()
        return value

    @classmethod
    def _json_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._json_value(item) for item in value]
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    @staticmethod
    def _bound_value(value: Any) -> Any:
        if isinstance(value, BindParameter):
            return value.value
        raise NotImplementedError("SQL expression values require an RPC function")

    def _criteria_params(self, criteria: list[Any]) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        for expression in criteria:
            if (
                isinstance(expression, BooleanClauseList)
                and expression.operator is operators.and_
            ):
                params.extend(self._criteria_params(list(expression.clauses)))
                continue
            if isinstance(expression, BooleanClauseList):
                params.append(
                    (
                        "or",
                        f"({','.join(self._logic(item) for item in expression.clauses)})",
                    )
                )
                continue
            column, predicate = self._simple_predicate(expression)
            params.append((column, predicate))
        return params

    def _logic(self, expression: Any) -> str:
        if isinstance(expression, BooleanClauseList):
            operator = "or" if expression.operator is operators.or_ else "and"
            return f"{operator}({','.join(self._logic(item) for item in expression.clauses)})"
        column, predicate = self._simple_predicate(expression)
        return f"{column}.{predicate}"

    def _simple_predicate(self, expression: Any) -> tuple[str, str]:
        left, right = list(expression.get_children())[:2]
        value = self._expression_value(right)
        operation = expression.operator
        operation_name = {
            operators.eq: "eq",
            operators.ne: "neq",
            operators.lt: "lt",
            operators.le: "lte",
            operators.gt: "gt",
            operators.ge: "gte",
            operators.is_: "is",
            operators.is_not: "not.is",
        }.get(operation)
        if operation in {operators.in_op, operators.not_in_op}:
            prefix = "in" if operation is operators.in_op else "not.in"
            values = ",".join(self._filter_value(item, quote=True) for item in value)
            return left.key, f"{prefix}.({values})"
        if operation_name is None:
            raise NotImplementedError(f"unsupported PostgREST predicate: {operation}")
        return left.key, f"{operation_name}.{self._filter_value(value)}"

    @staticmethod
    def _expression_value(value: Any) -> Any:
        if isinstance(value, BindParameter):
            return value.value
        if isinstance(value, Null):
            return None
        if isinstance(value, True_):
            return True
        if isinstance(value, False_):
            return False
        return getattr(value, "value", value)

    @classmethod
    def _filter_value(cls, value: Any, *, quote: bool = False) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (datetime, date)):
            text = value.isoformat()
        else:
            text = str(value)
        if quote:
            return '"' + text.replace('"', '\\"') + '"'
        return text

    @staticmethod
    def _compile_order(expression: Any) -> str:
        direction = "asc"
        column = expression
        if isinstance(expression, UnaryExpression):
            column = expression.element
            if expression.modifier is operators.desc_op:
                direction = "desc"
        return f"{column.key}.{direction}"

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise CloudBaseDataError(method.lower(), 503, type(exc).__name__) from exc
        if response.is_error:
            detail = "request rejected"
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail = str(body.get("message") or body.get("error") or detail)
            except ValueError:
                pass
            raise CloudBaseDataError(method.lower(), response.status_code, detail[:300])
        return response
