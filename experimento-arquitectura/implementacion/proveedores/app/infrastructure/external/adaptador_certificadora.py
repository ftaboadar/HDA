from app.common.config import settings
from app.infrastructure.external._base_http import _AdaptadorHttpGenerico


class AdaptadorCertificadora(_AdaptadorHttpGenerico):
    def __init__(self) -> None:
        super().__init__(settings.mock_certificadora_url)
