from __future__ import annotations

from html import escape


def render_app_page(
    *,
    title: str,
    heading: str,
    lede: str,
    active: str,
    body: str,
    scripts: list[str] | None = None,
    shell_class: str = "shell",
    body_class: str = "",
) -> str:
    script_tags = "\n".join(
        f'    <script src="{escape(src)}"></script>' for src in (scripts or [])
    )
    return f"""<!doctype html>
<html lang="id">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>{escape(title)}</title>
    <link rel="stylesheet" href="/static/styles.css"/>
  </head>
  <body class="{escape(body_class)}">
    <a class="skip" href="#main">Skip to content</a>
    {_nav(active)}
    <main id="main" class="{escape(shell_class)}">
      <header class="page-head">
        <h1>{escape(heading)}</h1>
        <p class="lede">{escape(lede)}</p>
      </header>
      {body}
    </main>
{script_tags}
  </body>
</html>
"""


def _nav(active: str) -> str:
    items = (
        ("claim", "/", "Claim invoice"),
        ("pks", "/agreements", "Upload PKS"),
        ("catalog", "/catalog", "PKS data"),
        ("compare", "/compare", "Compare"),
        ("review", "/review", "Tariff review"),
    )
    links = []
    for key, href, label in items:
        current = ' aria-current="page"' if key == active else ""
        links.append(f'<a href="{href}"{current}>{escape(label)}</a>')
    return f"""
    <header class="topbar">
      <div class="topbar-inner">
        <a class="mark" href="/">EPLKK</a>
        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
        <nav id="site-nav" class="site-nav">
          {"".join(links)}
        </nav>
      </div>
    </header>
    """
