"""
TelemetryRepository - Gerenciamento otimizado de dados de telemetria
Implementa batch inserts e limpeza de dados antigos
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from models.telemetry import DeviceTelemetry

class TelemetryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_telemetry(self, device_id: str, telemetry_data: dict) -> Optional[DeviceTelemetry]:
        """Salva um registro de telemetria"""
        telemetry = DeviceTelemetry(
            device_id=device_id,
            battery_level=telemetry_data.get("battery_level"),
            is_charging=telemetry_data.get("is_charging"),
            free_disk_space_mb=telemetry_data.get("free_disk_space_mb"),
            installed_apps=telemetry_data.get("installed_apps"),
            latitude=telemetry_data.get("latitude"),
            longitude=telemetry_data.get("longitude"),
            foreground_app=telemetry_data.get("foreground_app"),
            timestamp=datetime.utcnow()
        )
        self.db.add(telemetry)
        await self.db.flush()
        return telemetry

    async def save_telemetry_batch(self, telemetry_list: List[dict]) -> int:
        """
        Salva múltiplos registros de telemetria em batch
        Muito mais eficiente que salvar um por um
        
        Args:
            telemetry_list: Lista de dicts com {device_id, battery_level, ...}
        
        Returns:
            Quantidade de registros salvos
        """
        telemetry_objects = []
        
        for tel_data in telemetry_list:
            telemetry = DeviceTelemetry(
                device_id=tel_data["device_id"],
                battery_level=tel_data.get("battery_level"),
                is_charging=tel_data.get("is_charging"),
                free_disk_space_mb=tel_data.get("free_disk_space_mb"),
                installed_apps=tel_data.get("installed_apps"),
                latitude=tel_data.get("latitude"),
                longitude=tel_data.get("longitude"),
                foreground_app=tel_data.get("foreground_app"),
                timestamp=tel_data.get("timestamp", datetime.utcnow())
            )
            telemetry_objects.append(telemetry)
        
        self.db.add_all(telemetry_objects)
        await self.db.flush()
        return len(telemetry_objects)

    async def get_latest_telemetry(self, device_id: str) -> Optional[DeviceTelemetry]:
        """Obtém o registro de telemetria mais recente de um dispositivo"""
        query = select(DeviceTelemetry).where(
            DeviceTelemetry.device_id == device_id
        ).order_by(desc(DeviceTelemetry.timestamp)).limit(1)
        
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_telemetry_range(
        self, 
        device_id: str, 
        hours: int = 24
    ) -> List[DeviceTelemetry]:
        """Obtém telemetria dos últimas N horas"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(DeviceTelemetry).where(
            and_(
                DeviceTelemetry.device_id == device_id,
                DeviceTelemetry.timestamp >= cutoff_time
            )
        ).order_by(desc(DeviceTelemetry.timestamp))
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_all_latest_telemetry(self) -> List[Dict[str, Any]]:
        """Obtém o registro mais recente de TODOS os dispositivos (para dashboard)"""
        # Subquery para pegar o timestamp máximo de cada dispositivo
        subquery = select(
            DeviceTelemetry.device_id,
            func.max(DeviceTelemetry.timestamp).label('max_timestamp')
        ).group_by(DeviceTelemetry.device_id).subquery()
        
        query = select(DeviceTelemetry).join(
            subquery,
            and_(
                DeviceTelemetry.device_id == subquery.c.device_id,
                DeviceTelemetry.timestamp == subquery.c.max_timestamp
            )
        ).order_by(desc(DeviceTelemetry.timestamp))
        
        result = await self.db.execute(query)
        records = result.scalars().all()
        
        return [
            {
                'device_id': r.device_id,
                'battery_level': r.battery_level,
                'is_charging': r.is_charging,
                'free_disk_space_mb': r.free_disk_space_mb,
                'timestamp': r.timestamp,
                'latitude': r.latitude,
                'longitude': r.longitude,
                'foreground_app': r.foreground_app
            }
            for r in records
        ]

    async def cleanup_old_telemetry(self, days: int = 30) -> int:
        """
        Remove registros de telemetria mais antigos que N dias
        Ajuda a manter o banco otimizado
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        stmt = delete(DeviceTelemetry).where(
            DeviceTelemetry.timestamp < cutoff_time
        )
        
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    async def get_device_telemetry_stats(self, device_id: str, hours: int = 24) -> Dict[str, Any]:
        """Retorna estatísticas agregadas de telemetria"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(
            func.avg(DeviceTelemetry.battery_level).label('avg_battery'),
            func.max(DeviceTelemetry.battery_level).label('max_battery'),
            func.min(DeviceTelemetry.battery_level).label('min_battery'),
            func.avg(DeviceTelemetry.free_disk_space_mb).label('avg_disk_free'),
            func.count(DeviceTelemetry.id).label('checkin_count')
        ).where(
            and_(
                DeviceTelemetry.device_id == device_id,
                DeviceTelemetry.timestamp >= cutoff_time
            )
        )
        
        result = await self.db.execute(query)
        row = result.first()
        
        if not row:
            return {
                'avg_battery': None,
                'max_battery': None,
                'min_battery': None,
                'avg_disk_free': None,
                'checkin_count': 0
            }
        
        return {
            'avg_battery': float(row[0]) if row[0] else None,
            'max_battery': float(row[1]) if row[1] else None,
            'min_battery': float(row[2]) if row[2] else None,
            'avg_disk_free': int(row[3]) if row[3] else None,
            'checkin_count': row[4]
        }

    async def get_telemetry_by_id(self, telemetry_id: int) -> Optional[DeviceTelemetry]:
        """Obtém um registro específico de telemetria por ID"""
        query = select(DeviceTelemetry).where(DeviceTelemetry.id == telemetry_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def delete_device_telemetry(self, device_id: str) -> int:
        """Remove toda a telemetria de um dispositivo"""
        stmt = delete(DeviceTelemetry).where(
            DeviceTelemetry.device_id == device_id
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount
