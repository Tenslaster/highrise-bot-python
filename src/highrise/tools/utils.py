from ..models.websocket.highrise_models import TipType, TIP_VALUES

class Utils:
    """Stateless helper functions used across the SDK."""

    @staticmethod
    def split_tip(amount: int) -> list[TipType]:
        """Decomposes an amount into the largest valid tip tiers, greedily."""
        if amount <= 0:
            return []

        tiers = sorted(TIP_VALUES.items(), reverse=True)
        result: list[TipType] = []

        for value, tier in tiers:
            while amount >= value:
                result.append(tier)
                amount -= value

        return result

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format time from raw seconds to human readable format (`4d 14h 40m 12s`)"""

        seconds = int(seconds)

        seconds_formatted = seconds % 60
        minutes = (seconds // 60) % 60
        hours = (seconds // 3600) % 24
        days = seconds // 86400

        parts = []
        if days > 0: parts.append(f"{days}d")
        if hours > 0: parts.append(f"{hours}h")
        if minutes > 0: parts.append(f"{minutes}m")
        if seconds_formatted > 0 or len(parts) == 0: parts.append(f"{seconds_formatted}s")

        return ", ".join(parts)