from typing import Generator
from app.contracts.services import (
    SlskdClientContract, SearchProviderContract, SearchExecutorContract
)
from app.services.slskd import SlskdClient
from app.services.search_ranking_service import SearchRankingService
from app.services.fallback_search_executor import FallbackSearchExecutor

def get_slskd_client() -> SlskdClientContract:
    """
    [CDA-003] Dependency Injection provider for SlskdClient.
    Returns concrete implementation bound to SlskdClientContract interface.
    """
    return SlskdClient()


def get_search_provider() -> SearchProviderContract:
    """
    [CDA-003] Dependency Injection provider for SearchProvider.
    Returns SearchRankingService concrete class bound to SearchProviderContract.
    """
    return SearchRankingService()


def get_search_executor() -> SearchExecutorContract:
    """
    [CDA-003] Dependency Injection provider for FallbackSearchExecutor.
    Injects SlskdClientContract and SearchProviderContract dependencies automatically.
    """
    return FallbackSearchExecutor(
        slskd_client=get_slskd_client(),
        search_provider=get_search_provider()
    )
