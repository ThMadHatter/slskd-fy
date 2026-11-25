from app.contracts.services import SlskdClientContract
from app.services.slskd import SlskdClient

def get_slskd_client() -> SlskdClientContract:
    """
    [CDA-003] Dependency Injection provider for SlskdClient.
    Returns concrete implementation bound to SlskdClientContract interface.
    """
    return SlskdClient()
