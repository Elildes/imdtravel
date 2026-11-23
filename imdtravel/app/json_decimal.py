"""JSON com Decimal: os números saem exatamente como chegaram das dependências.

O AirlinesHub manda "priceUSD": 350.50. Com float, o Python devolveria 350.5; com
Decimal + simplejson (use_decimal), devolvemos 350.50, o mesmo texto da origem.
"""
import simplejson
from flask.json.provider import DefaultJSONProvider


class DecimalJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault("default", self.default)
        kwargs.setdefault("ensure_ascii", self.ensure_ascii)
        kwargs.setdefault("sort_keys", self.sort_keys)
        return simplejson.dumps(obj, use_decimal=True, **kwargs)

    def loads(self, s, **kwargs):
        return simplejson.loads(s, use_decimal=True, **kwargs)
