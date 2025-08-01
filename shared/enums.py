from enum import Enum

class TicketType(Enum):
    SUPPORT = "support"
    REPORT = "report"
    SUGGESTION = "suggestion"

class VoteType(Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"
