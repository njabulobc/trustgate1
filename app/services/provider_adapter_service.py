from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings


class ProviderAdapterError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_response: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_response = provider_response


class ScreeningSubjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(default="subject_1", min_length=1, max_length=100)
    subject_kind: str = Field(..., pattern="^(individual|company)$")
    primary_name: str = Field(..., min_length=1, max_length=255)

    alternate_names: list[str] = Field(default_factory=list)
    date_of_birth: str | None = None
    nationality: str | None = None
    country: str | None = None
    national_id_number: str | None = None
    registration_number: str | None = None
    address: str | None = None


class ProviderScreeningCandidate(BaseModel):
    provider_candidate_id: str | None = None
    provider_entity_id: str | None = None
    matched_name: str
    match_score: float | None = None
    list_name: str | None = None
    dataset: str | None = None
    country: str | None = None
    notes: str | None = None
    candidate_payload: dict[str, Any] | None = None


class ProviderScreeningResult(BaseModel):
    query_id: str
    subject_name: str
    candidates: list[ProviderScreeningCandidate] = Field(default_factory=list)


class ProviderBatchScreeningResponse(BaseModel):
    provider_name: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    results: list[ProviderScreeningResult] = Field(default_factory=list)


class OpenSanctionsAdapter:
    provider_name = "opensanctions"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = (base_url or settings.OPENSANCTIONS_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.OPENSANCTIONS_API_KEY.get_secret_value()
        self.timeout = httpx.Timeout(timeout_seconds)

    async def screen_subject(
        self,
        subject: ScreeningSubjectInput,
        *,
        dataset: str = "default",
        threshold: float | None = None,
        limit: int = 5,
    ) -> ProviderBatchScreeningResponse:
        return await self.screen_subjects(
            subjects=[subject],
            dataset=dataset,
            threshold=threshold,
            limit=limit,
        )

    async def screen_subjects(
        self,
        subjects: list[ScreeningSubjectInput],
        *,
        dataset: str = "default",
        threshold: float | None = None,
        limit: int = 5,
    ) -> ProviderBatchScreeningResponse:
        if not subjects:
            raise ProviderAdapterError("At least one screening subject is required.")

        query_ids = [subject.query_id for subject in subjects]
        if len(query_ids) != len(set(query_ids)):
            raise ProviderAdapterError("Each screening subject must have a unique query_id.")

        request_payload = {
            "queries": {
                subject.query_id: self._build_provider_query(subject)
                for subject in subjects
            }
        }

        response_payload = await self._post_match_request(
            dataset=dataset,
            payload=request_payload,
            threshold=threshold if threshold is not None else settings.SCREENING_MIN_SCORE,
            limit=limit,
        )

        normalized_results = [
            self._normalize_result(
                query_id=subject.query_id,
                subject_name=subject.primary_name,
                response_payload=response_payload,
            )
            for subject in subjects
        ]

        return ProviderBatchScreeningResponse(
            provider_name=self.provider_name,
            request_payload=request_payload,
            response_payload=response_payload,
            results=normalized_results,
        )

    def _build_provider_query(self, subject: ScreeningSubjectInput) -> dict[str, Any]:
        properties: dict[str, list[str]] = {"name": [subject.primary_name]}

        alternate_names = [name for name in subject.alternate_names if name and name != subject.primary_name]
        if alternate_names:
            properties["name"].extend(alternate_names)

        if subject.address:
            properties["address"] = [subject.address]

        if subject.subject_kind == "individual":
            if subject.date_of_birth:
                properties["birthDate"] = [subject.date_of_birth]
            if subject.nationality:
                properties["nationality"] = [subject.nationality]
            if subject.national_id_number:
                properties["idNumber"] = [subject.national_id_number]

            schema = "Person"
        else:
            if subject.country:
                properties["jurisdiction"] = [subject.country]
            if subject.registration_number:
                properties["registrationNumber"] = [subject.registration_number]

            schema = "Company"

        return {
            "schema": schema,
            "properties": properties,
        }

    async def _post_match_request(
        self,
        *,
        dataset: str,
        payload: dict[str, Any],
        threshold: float,
        limit: int,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/match/{dataset}"
        params = {
            "threshold": threshold,
            "limit": limit,
        }
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    params=params,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderAdapterError("OpenSanctions request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text[:2000] if exc.response is not None else None
            raise ProviderAdapterError(
                "OpenSanctions returned an error response.",
                status_code=exc.response.status_code if exc.response is not None else None,
                provider_response=response_text,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError("Failed to reach OpenSanctions.") from exc

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise ProviderAdapterError(
                "OpenSanctions returned an invalid JSON response.",
                status_code=response.status_code,
                provider_response=response.text[:2000],
            ) from exc

        if not isinstance(response_payload, dict):
            raise ProviderAdapterError(
                "OpenSanctions returned an unexpected response structure.",
                status_code=response.status_code,
                provider_response=response_payload,
            )

        responses = response_payload.get("responses")
        if not isinstance(responses, dict):
            raise ProviderAdapterError(
                "OpenSanctions response is missing the expected 'responses' object.",
                status_code=response.status_code,
                provider_response=response_payload,
            )

        return response_payload

    def _normalize_result(
        self,
        *,
        query_id: str,
        subject_name: str,
        response_payload: dict[str, Any],
    ) -> ProviderScreeningResult:
        responses = response_payload.get("responses", {})
        raw_result = responses.get(query_id, {})

        if not isinstance(raw_result, dict):
            raise ProviderAdapterError(
                f"OpenSanctions returned an invalid result block for query_id '{query_id}'.",
                provider_response=raw_result,
            )

        raw_candidates = raw_result.get("results", [])
        if not isinstance(raw_candidates, list):
            raise ProviderAdapterError(
                f"OpenSanctions returned invalid candidate results for query_id '{query_id}'.",
                provider_response=raw_result,
            )

        candidates = [
            self._normalize_candidate(candidate)
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]

        return ProviderScreeningResult(
            query_id=query_id,
            subject_name=subject_name,
            candidates=candidates,
        )

    def _normalize_candidate(self, candidate: dict[str, Any]) -> ProviderScreeningCandidate:
        properties = candidate.get("properties")
        properties = properties if isinstance(properties, dict) else {}

        provider_entity_id = self._safe_string(candidate.get("id"))
        matched_name = (
            self._safe_string(candidate.get("caption"))
            or self._first_property_value(properties, "name")
            or provider_entity_id
            or "Unknown"
        )
        match_score = self._safe_float(candidate.get("score"))
        dataset = self._first_list_value(candidate.get("datasets"))
        country = (
            self._first_property_value(properties, "country")
            or self._first_property_value(properties, "nationality")
            or self._first_property_value(properties, "jurisdiction")
        )

        return ProviderScreeningCandidate(
            provider_candidate_id=provider_entity_id,
            provider_entity_id=provider_entity_id,
            matched_name=matched_name,
            match_score=match_score,
            list_name=None,
            dataset=dataset,
            country=country,
            notes=self._build_notes(candidate),
            candidate_payload=candidate,
        )

    @staticmethod
    def _first_property_value(properties: dict[str, Any], key: str) -> str | None:
        value = properties.get(key)
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _first_list_value(value: Any) -> str | None:
        if isinstance(value, list) and value:
            return str(value[0])
        return None

    @staticmethod
    def _safe_string(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_notes(candidate: dict[str, Any]) -> str | None:
        notes: list[str] = []

        schema = candidate.get("schema")
        if schema:
            notes.append(f"schema={schema}")

        topics = candidate.get("topics")
        if isinstance(topics, list) and topics:
            notes.append(f"topics={','.join(str(topic) for topic in topics)}")

        return "; ".join(notes) if notes else None


async def screen_subject(
    subject: ScreeningSubjectInput,
    *,
    dataset: str = "default",
    threshold: float | None = None,
    limit: int = 5,
) -> ProviderBatchScreeningResponse:
    adapter = OpenSanctionsAdapter()
    return await adapter.screen_subject(
        subject=subject,
        dataset=dataset,
        threshold=threshold,
        limit=limit,
    )


async def screen_subjects(
    subjects: list[ScreeningSubjectInput],
    *,
    dataset: str = "default",
    threshold: float | None = None,
    limit: int = 5,
) -> ProviderBatchScreeningResponse:
    adapter = OpenSanctionsAdapter()
    return await adapter.screen_subjects(
        subjects=subjects,
        dataset=dataset,
        threshold=threshold,
        limit=limit,
    )


__all__ = [
    "OpenSanctionsAdapter",
    "ProviderAdapterError",
    "ProviderBatchScreeningResponse",
    "ProviderScreeningCandidate",
    "ProviderScreeningResult",
    "ScreeningSubjectInput",
    "screen_subject",
    "screen_subjects",
]