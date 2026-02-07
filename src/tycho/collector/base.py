"""Abstract collector interface."""

from abc import ABC, abstractmethod

from tycho.models import Job


class BaseCollector(ABC):
    """Base class for job collectors."""

    @abstractmethod
    def collect(
        self,
        search_terms: list[str],
        locations: list[str],
        results_wanted: int = 50,
    ) -> list[Job]:
        """Collect jobs from the source."""
        ...
