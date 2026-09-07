"""Root URLconf.

Routes are added by the slice that creates the interface they serve; `config/` wires
`interfaces/*` entry points and the reverse edge stays forbidden (item 3 §7.2, L16).
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver

urlpatterns: list[URLPattern | URLResolver] = []
