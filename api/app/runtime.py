from __future__ import annotations

from dataclasses import dataclass

from .repository import AssessmentRepository
from .services.catalog import MovementCatalog
from .services.scoring.service import ScoringService
from .settings import AppSettings


@dataclass(slots=True)
class RuntimeState:
    settings: AppSettings
    repository: AssessmentRepository
    catalog: MovementCatalog
    scoring_service: ScoringService

