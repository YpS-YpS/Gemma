# -*- coding: utf-8 -*-
"""
Event system for real-time updates between components
"""

import asyncio
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Callable, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for the system"""
    SUT_DISCOVERED = "sut_discovered"
    SUT_ONLINE = "sut_online"
    SUT_OFFLINE = "sut_offline"
    SUT_STATUS_CHANGED = "sut_status_changed"
    AUTOMATION_STARTED = "automation_started"
    AUTOMATION_COMPLETED = "automation_completed"
    AUTOMATION_FAILED = "automation_failed"
    OMNIPARSER_STATUS_CHANGED = "omniparser_status_changed"


@dataclass
class Event:
    """Event data structure"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime
    source: str = "backend"


class EventBus:
    """Central event bus for real-time communication between components"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """Subscribe to an event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.value}")
        
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """Unsubscribe from an event type"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)
            
    def emit(self, event_type: EventType, data: Dict[str, Any], source: str = "backend"):
        """Emit an event to all subscribers"""
        event = Event(
            event_type=event_type,
            data=data,
            timestamp=datetime.now(),
            source=source
        )
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
            
        # Notify subscribers
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in event callback for {event_type.value}: {e}")
                    
        logger.debug(f"Emitted event: {event_type.value} from {source}")
        
    def get_recent_events(self, count: int = 50) -> List[Event]:
        """Get recent events"""
        return self._event_history[-count:]


# Global event bus instance
event_bus = EventBus()