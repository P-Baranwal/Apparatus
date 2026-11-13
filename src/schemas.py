from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

RegistrationStatus = Literal["accepted", "waiting_list", "pending", "cancelled", "rejected"]
CompetitionStatus = Literal["upcoming", "in_progress", "past", "cancelled"]
ResultKind = Literal["single", "average"]
DelegateStatus = Literal["senior", "regional", "full", "junior", "trainee"]

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class ErrorBody(BaseModel):
    detail: str
    code: str | None = None


# --- reads: persons -------------------------------------------------------


class PersonListItem(BaseModel):
    person_no: int
    wca_id: str | None
    name: str
    country_id: str
    country_name: str
    competitions_count: int
    podiums_count: int


class PersonalRecord(BaseModel):
    event_id: str
    event_name: str
    best: int | None
    average: int | None
    world_rank: int | None
    continental_rank: int | None
    national_rank: int | None


class PersonDetail(BaseModel):
    person_no: int
    wca_id: str | None
    name: str
    local_name: str | None
    gender: str
    country_id: str
    country_name: str
    since_date: date | None
    delegate_status: DelegateStatus | None
    personal_records: list[PersonalRecord]


class PersonResultItem(BaseModel):
    result_id: str
    competition_id: str
    competition_name: str
    event_id: str
    round_number: int
    position: int | None
    best: int
    average: int | None
    single_record: str | None
    average_record: str | None
    country_id: str


# --- reads: competitions --------------------------------------------------


class RoundItem(BaseModel):
    round_number: int
    format_id: str
    format_name: str
    per_attempt: int | None
    cutoff_attempts: int | None
    cutoff_value: int | None
    adv_type: str | None
    adv_level: int | None
    is_dual: bool
    is_head_to_head: bool
    last_day: date | None


class CompetitionEvent(BaseModel):
    event_id: str
    event_name: str
    result_kind: str
    rounds: list[RoundItem]


class PersonRef(BaseModel):
    person_no: int
    name: str
    wca_id: str | None


class PodiumItem(BaseModel):
    event_id: str
    event_name: str
    position: int
    person_no: int
    name: str
    wca_id: str | None
    country_id: str
    best: int
    average: int | None
    single_record: str | None
    average_record: str | None


class CompetitionListItem(BaseModel):
    competition_id: str
    name: str
    city: str | None
    country_id: str
    country_name: str
    continent_id: str
    start_date: date
    end_date: date
    status: CompetitionStatus
    competitor_limit: int | None
    registered_count: int
    main_event_id: str | None
    championship_type: str | None


class CompetitionDetail(CompetitionListItem):
    short_name: str | None
    venue_name: str | None
    street_address: str | None
    venue_details: str | None
    latitude: float | None
    longitude: float | None
    website: str | None
    opens_at: datetime | None
    closes_at: datetime | None
    amount: int | None
    currency_code: str | None
    refund_policy_percent: int | None
    announced_at: datetime | None
    cancelled_at: datetime | None
    results_posted_at: datetime | None
    events: list[CompetitionEvent]
    delegates: list[PersonRef]
    organizers: list[PersonRef]
    podiums: list[PodiumItem]


class CompetitionResultItem(BaseModel):
    result_id: str
    event_id: str
    round_number: int
    position: int | None
    person_no: int
    name: str
    wca_id: str | None
    country_id: str
    best: int
    average: int | None
    single_record: str | None
    average_record: str | None
    solves: list[int]


# --- reads: rankings, search, lookups, stats ------------------------------


class RankingItem(BaseModel):
    rank: int
    person_no: int
    name: str
    wca_id: str | None
    country_id: str
    country_name: str
    best: int
    average: int | None
    competition_id: str
    competition_name: str
    continental_rank: int | None
    national_rank: int | None


class SearchCompetition(BaseModel):
    competition_id: str
    name: str
    city: str | None
    country_id: str
    start_date: date


class SearchPerson(BaseModel):
    person_no: int
    wca_id: str | None
    name: str
    country_id: str


class SearchResults(BaseModel):
    competitions: list[SearchCompetition]
    persons: list[SearchPerson]


class CountryItem(BaseModel):
    country_id: str
    iso2: str | None
    name: str
    continent_id: str
    continent_name: str


class MedalRow(BaseModel):
    country_id: str
    country_name: str
    continent_id: str
    gold: int
    silver: int
    bronze: int
    total: int


class CountryYearRow(BaseModel):
    country_id: str
    country_name: str
    year: int
    competition_count: int


class RecordRow(BaseModel):
    event_id: str
    event_name: str
    kind: ResultKind
    record_code: str
    count: int


# --- reads: registrations -------------------------------------------------


class RegistrationItem(BaseModel):
    competition_id: str
    registrant_no: int
    person_no: int
    name: str
    wca_id: str | None
    status: RegistrationStatus
    registered_at: datetime
    guests: int
    guardian_consent: bool
    events: list[str]


class RegistrationStatusPromotion(BaseModel):
    registrant_no: int
    person_no: int
    name: str


class RegistrationChange(BaseModel):
    registration: RegistrationItem
    promoted: RegistrationStatusPromotion | None = None


# --- writes ---------------------------------------------------------------


class RegistrationCreate(BaseModel):
    person_no: int = Field(ge=1)
    events: list[str] = Field(min_length=1, max_length=17)
    guests: int = Field(default=0, ge=0, le=10)


class RegistrationStatusUpdate(BaseModel):
    status: RegistrationStatus


class PersonCountryUpdate(BaseModel):
    country_id: str = Field(min_length=1, max_length=60)
