"""自定义 Action / Recognition / Sink 注册入口。"""

from agent.custom.action import (
    CleanupCustomImg,
    CleanupCustomLog,
    CleanupMaafwBakLogs,
    CleanupOnErrorImg,
    CleanupVisionImg,
    CounterIncrement,
    GoIntoEntry,
    GoIntoEntryByGuide,
    NonlinearSwipe,
    RetryFailed,
    RetryFaild,
    Screenshot,
    StopTaskList,
)
from agent.custom.reco import (
    FindAccessoryFlipTicket,
    FindBondsWithoutEnoughToken,
    FindGearFlipTicket,
    FindPlantableFlower,
    FindToChallenge,
    FlipCard,
    IsCounterOverflow,
    IsInNinjaGuide,
    MissionOfficeStrategy,
    SecretRealmTicket,
)
from agent.custom.sink import AspectRatioChecker

__all__ = [
    # action
    "StopTaskList",
    "Screenshot",
    "RetryFailed",
    "RetryFaild",
    "GoIntoEntry",
    "GoIntoEntryByGuide",
    "CounterIncrement",
    "NonlinearSwipe",
    "CleanupMaafwBakLogs",
    "CleanupOnErrorImg",
    "CleanupVisionImg",
    "CleanupCustomImg",
    "CleanupCustomLog",
    # reco
    "IsCounterOverflow",
    "IsInNinjaGuide",
    "FindToChallenge",
    "FindPlantableFlower",
    "FlipCard",
    "FindBondsWithoutEnoughToken",
    "FindAccessoryFlipTicket",
    "FindGearFlipTicket",
    "SecretRealmTicket",
    "MissionOfficeStrategy",
    # sink
    "AspectRatioChecker",
]
