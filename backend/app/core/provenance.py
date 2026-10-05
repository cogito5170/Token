"""Provenance of every number (docs/architecture.md section 4). Part of the contract: same values as the
`provenance` enum in docs/schema.sql and components.schemas.Provenance in docs/api/openapi.yaml."""
from enum import Enum


class Provenance(str, Enum):
    MEASURED = "MEASURED"
    CALCULATED = "CALCULATED"
    ESTIMATED = "ESTIMATED"
    SIMULATED = "SIMULATED"


# strongest first: a value combined from two provenances takes the weaker one
STRENGTH = (Provenance.MEASURED, Provenance.CALCULATED, Provenance.ESTIMATED, Provenance.SIMULATED)


def weaker(a: Provenance, b: Provenance) -> Provenance:
    return max(a, b, key=STRENGTH.index)
