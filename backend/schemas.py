from typing import Literal, Optional
from pydantic import BaseModel, Field


class RiderConfig(BaseModel):
    mass: float = Field(gt=0, description="Combined rider + bike mass (kg)")
    ftp: float = Field(gt=0, description="Functional threshold power (W)")
    cda: float = Field(ge=0, description="Drag area (m²)")
    crr: float = Field(ge=0, description="Rolling resistance coefficient")


class EnvironmentConfig(BaseModel):
    windSpeed: float = 0.0
    windBearing: float = 0.0
    temperature: float = 20.0
    airDensity: float = 1.225


class StrategyConfig(BaseModel):
    type: Literal["constant_power"] = "constant_power"
    targetPower: float = Field(gt=0)


class SimSettings(BaseModel):
    timeStepS: float = Field(default=1.0, gt=0, le=10)
    tickIntervalMs: int = Field(default=250, ge=16)


class SimConfigPayload(BaseModel):
    routeId: str
    rider: Optional[RiderConfig] = None
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    strategy: StrategyConfig
    simSettings: SimSettings = Field(default_factory=SimSettings)


class SimCreateRequest(BaseModel):
    config: SimConfigPayload
    riderId: Optional[str] = None


class TelemetryPoint(BaseModel):
    t: float
    dist: float
    speed: float
    targetPower: float
    realizedPower: float
    elevation: float
    grade: float
    gravForce: float
    rollingForce: float
    aeroForce: float
    totalEnergy: float
    forceLimited: bool = False
    limitReason: Optional[str] = None
    kcalBurned: float = 0.0


class SegmentResult(BaseModel):
    name: str
    distStartKm: float
    distEndKm: float
    avgSpeedKph: float
    avgRealizedPower: float
    avgGrade: float
    timeS: float


class SimSummary(BaseModel):
    totalTimeS: float
    totalDistKm: float
    avgSpeedKph: float
    avgRealizedPower: float
    maxSpeedKph: float
    totalEnergyKj: float
    avgGrade: float
    normPower: float
    kcalBurned: float = 0.0
    stopReason: Optional[str] = None
    segments: list[SegmentResult] = []


class SimulationCreated(BaseModel):
    simId: str
    status: str
    createdAt: str
    routeName: str
    totalDistanceKm: float


class SimulationState(BaseModel):
    simId: str
    status: str
    tickCount: int
    latest: Optional[TelemetryPoint] = None
    summary: Optional[SimSummary] = None
