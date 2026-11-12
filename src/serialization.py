from datetime import date, datetime, time
from decimal import Decimal


def to_jsonable(o):
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (datetime, date, time)):
        return o.isoformat()
    if hasattr(o, "to_native"):
        return to_jsonable(o.to_native())
    if o.__class__.__name__ == "ObjectId":
        return str(o)
    return o
