from dataclasses import dataclass, field

@dataclass
class PlayerRecord:
    """Mutable rating state for a single player (batter or pitcher)."""
    rating: float
    instances: int = 0