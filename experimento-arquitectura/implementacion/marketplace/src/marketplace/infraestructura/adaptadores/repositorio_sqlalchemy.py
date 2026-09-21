from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import declarative_base, sessionmaker
from marketplace.dominio.repositorios import RepositorioMarketplace
from marketplace.dominio.entidades import Marketplace
import uuid

Base = declarative_base()


class MarketplaceModel(Base):
    __tablename__ = "marketplace"
    id = Column(String, primary_key=True)
    solicitud_id = Column(String, unique=True)
    proveedor_seleccionado_id = Column(String, nullable=True)


class RepositorioMarketplaceSQLAlchemy(RepositorioMarketplace):
    def __init__(self, db_url="sqlite:///marketplace.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def obtener_por_solicitud_id(self, solicitud_id: uuid.UUID) -> Marketplace:
        session = self.Session()
        model = (
            session.query(MarketplaceModel)
            .filter_by(solicitud_id=str(solicitud_id))
            .first()
        )
        session.close()
        if model:
            mkp = Marketplace(
                id=uuid.UUID(model.id), solicitud_id=uuid.UUID(model.solicitud_id)
            )
            if model.proveedor_seleccionado_id:
                mkp.proveedor_seleccionado_id = uuid.UUID(
                    model.proveedor_seleccionado_id
                )
            return mkp
        return Marketplace(solicitud_id=solicitud_id)

    def guardar(self, marketplace: Marketplace):
        session = self.Session()
        model = (
            session.query(MarketplaceModel)
            .filter_by(solicitud_id=str(marketplace.solicitud_id))
            .first()
        )
        if not model:
            model = MarketplaceModel(
                id=str(marketplace.id), solicitud_id=str(marketplace.solicitud_id)
            )
            session.add(model)
        if marketplace.proveedor_seleccionado_id:
            model.proveedor_seleccionado_id = str(marketplace.proveedor_seleccionado_id)
        session.commit()
        session.close()
