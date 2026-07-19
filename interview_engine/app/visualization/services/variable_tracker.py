from typing import Any, Dict, List

class VariableTracker:
    def histories(self, snapshots: List[Dict[str, Any]]) -> List[Dict[str, List[Any]]]:
        history: Dict[str, List[Any]] = {}
        result = []
        for snapshot in snapshots:
            for name, value in snapshot.items():
                values = history.setdefault(name, [])
                if not values or values[-1] != value:
                    values.append(value)
            result.append({key: list(values) for key, values in history.items()})
        return result
