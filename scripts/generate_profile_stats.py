import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path


USERNAME = os.environ.get("GITHUB_USERNAME", "aaron-z-chiu")
TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT_DIR = Path("assets")

# 不想计入语言统计的 repo 可以写在这里
EXCLUDED_REPOS = {
    USERNAME,  # 排除 profile README repo
}

# 如果以后觉得 TeX / HTML 等干扰太大，可以加进这里
EXCLUDED_LANGUAGES = {
    # "TeX",
    # "HTML",
}

TOP_N_LANGUAGES = 6


LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "C++": "#f34b7d",
    "C": "#555555",
    "Java": "#b07219",
    "MATLAB": "#e16737",
    "TeX": "#3D6117",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B",
    "Rust": "#dea584",
    "Go": "#00ADD8",
}


def github_request(url, method="GET", data=None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-profile-stats",
    }

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        body = None

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(request) as response:
        return json.load(response)


def get_user():
    return github_request(
        f"https://api.github.com/users/{urllib.parse.quote(USERNAME)}"
    )


def get_public_repos():
    repos = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{urllib.parse.quote(USERNAME)}/repos"
            f"?type=owner&per_page=100&page={page}"
        )

        batch = github_request(url)

        if not batch:
            break

        repos.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return repos


def search_count(query):
    params = urllib.parse.urlencode(
        {
            "q": query,
            "per_page": 1,
        }
    )

    result = github_request(
        f"https://api.github.com/search/issues?{params}"
    )

    return result["total_count"]


def get_last_year_contributions():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """

    variables = {
        "login": USERNAME,
        "from": start.isoformat(),
        "to": now.isoformat(),
    }

    try:
        result = github_request(
            "https://api.github.com/graphql",
            method="POST",
            data={
                "query": query,
                "variables": variables,
            },
        )

        return result["data"]["user"]["contributionsCollection"][
            "contributionCalendar"
        ]["totalContributions"]

    except Exception as exc:
        print(f"Warning: could not retrieve contribution count: {exc}")
        return None


def get_language_totals(repos):
    totals = defaultdict(int)

    for repo in repos:
        name = repo["name"]

        if repo["fork"]:
            continue

        if repo["archived"]:
            continue

        if name in EXCLUDED_REPOS:
            continue

        print(f"Reading languages: {name}")

        languages = github_request(
            f"https://api.github.com/repos/"
            f"{urllib.parse.quote(USERNAME)}/"
            f"{urllib.parse.quote(name)}/languages"
        )

        for language, byte_count in languages.items():
            if language in EXCLUDED_LANGUAGES:
                continue

            totals[language] += byte_count

    return totals


def compact_number(value):
    if value is None:
        return "—"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"

    if value >= 1_000:
        return f"{value / 1_000:.1f}k"

    return str(value)


def svg_header(width, height):
    return f"""<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}"
    role="img"
>
<style>
    .card {{
        fill: #ffffff;
        stroke: #d0d7de;
        stroke-width: 1;
    }}

    .title {{
        fill: #1f2328;
        font: 600 18px -apple-system, BlinkMacSystemFont,
              "Segoe UI", Helvetica, Arial, sans-serif;
    }}

    .label {{
        fill: #656d76;
        font: 400 12px -apple-system, BlinkMacSystemFont,
              "Segoe UI", Helvetica, Arial, sans-serif;
    }}

    .value {{
        fill: #1f2328;
        font: 600 22px -apple-system, BlinkMacSystemFont,
              "Segoe UI", Helvetica, Arial, sans-serif;
    }}

    .language {{
        fill: #1f2328;
        font: 400 13px -apple-system, BlinkMacSystemFont,
              "Segoe UI", Helvetica, Arial, sans-serif;
    }}

    @media (prefers-color-scheme: dark) {{
        .card {{
            fill: #0d1117;
            stroke: #30363d;
        }}

        .title,
        .value,
        .language {{
            fill: #e6edf3;
        }}

        .label {{
            fill: #8d96a0;
        }}
    }}
</style>
"""


def generate_stats_svg(stats):
    width = 460
    height = 180

    metrics = [
        (
            compact_number(stats["contributions"]),
            "Contributions · last year",
        ),
        (
            compact_number(stats["public_repos"]),
            "Public repositories",
        ),
        (
            compact_number(stats["pull_requests"]),
            "Pull requests",
        ),
        (
            compact_number(stats["issues"]),
            "Issues",
        ),
    ]

    svg = svg_header(width, height)

    svg += f"""
<rect class="card"
      x="0.5"
      y="0.5"
      width="{width - 1}"
      height="{height - 1}"
      rx="8"/>

<text class="title" x="20" y="31">
    GitHub Activity
</text>
"""

    positions = [
        (20, 73),
        (240, 73),
        (20, 135),
        (240, 135),
    ]

    for (value, label), (x, y) in zip(metrics, positions):
        svg += f"""
<text class="value" x="{x}" y="{y}">
    {escape(value)}
</text>

<text class="label" x="{x}" y="{y + 20}">
    {escape(label)}
</text>
"""

    svg += "</svg>\n"

    return svg


def generate_languages_svg(language_totals):
    width = 460
    height = 180

    total = sum(language_totals.values())

    sorted_languages = sorted(
        language_totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_languages = sorted_languages[:TOP_N_LANGUAGES]

    svg = svg_header(width, height)

    svg += f"""
<rect class="card"
      x="0.5"
      y="0.5"
      width="{width - 1}"
      height="{height - 1}"
      rx="8"/>

<text class="title" x="20" y="31">
    Most Used Languages
</text>
"""

    if total == 0:
        svg += """
<text class="label" x="20" y="80">
    No language data available.
</text>
</svg>
"""
        return svg

    bar_x = 20
    bar_y = 50
    bar_width = 420
    bar_height = 10

    current_x = bar_x

    for language, count in top_languages:
        fraction = count / total
        width_piece = bar_width * fraction
        color = LANGUAGE_COLORS.get(language, "#8c959f")

        svg += f"""
<rect
    x="{current_x:.2f}"
    y="{bar_y}"
    width="{width_piece:.2f}"
    height="{bar_height}"
    fill="{color}"
    rx="2"
/>
"""
        current_x += width_piece

    # 两列语言列表
    for index, (language, count) in enumerate(top_languages):
        percentage = count / total * 100

        column = index % 2
        row = index // 2

        x = 20 + column * 220
        y = 88 + row * 27

        color = LANGUAGE_COLORS.get(language, "#8c959f")

        svg += f"""
<circle
    cx="{x + 5}"
    cy="{y - 4}"
    r="5"
    fill="{color}"
/>

<text class="language"
      x="{x + 17}"
      y="{y}">
    {escape(language)}
</text>

<text class="label"
      x="{x + 155}"
      y="{y}">
    {percentage:.1f}%
</text>
"""

    svg += "</svg>\n"

    return svg


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating profile statistics for @{USERNAME}")

    user = get_user()
    repos = get_public_repos()

    original_repos = [
        repo
        for repo in repos
        if not repo["fork"] and not repo["archived"]
    ]

    stats = {
        "public_repos": len(original_repos),
        "pull_requests": search_count(
            f"author:{USERNAME} type:pr"
        ),
        "issues": search_count(
            f"author:{USERNAME} type:issue"
        ),
        "contributions": get_last_year_contributions(),
    }

    language_totals = get_language_totals(repos)

    stats_svg = generate_stats_svg(stats)
    languages_svg = generate_languages_svg(language_totals)

    (OUTPUT_DIR / "github-stats.svg").write_text(
        stats_svg,
        encoding="utf-8",
    )

    (OUTPUT_DIR / "top-languages.svg").write_text(
        languages_svg,
        encoding="utf-8",
    )

    print("Generated:")
    print("  assets/github-stats.svg")
    print("  assets/top-languages.svg")


if __name__ == "__main__":
    main()
