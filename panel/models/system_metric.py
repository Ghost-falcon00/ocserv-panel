from sqlalchemy import Column, Integer, Float, DateTime
from sqlalchemy.sql import func
from .database import Base

class SystemMetric(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    cpu_percent = Column(Float, default=0.0)
    ram_percent = Column(Float, default=0.0)
    disk_percent = Column(Float, default=0.0)

    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat() + "Z" if self.timestamp and not self.timestamp.tzinfo else (self.timestamp.isoformat() if self.timestamp else None),
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "disk_percent": self.disk_percent
        }
