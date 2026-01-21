"""
Sports News Tool for fetching current sports scores and schedules.

Fetches data from PlainTextSports.com which provides real-time scores,
schedules, and standings in a clean plain-text format.
"""

import logging

from django.utils import timezone

from .base import ZoeaTool, with_telemetry

logger = logging.getLogger(__name__)


class SportsNewsTool(ZoeaTool):
    """
    Tool for fetching current sports news, scores, and schedules.

    Uses PlainTextSports.com to get real-time sports data in plain text format.
    Supports NBA, NFL, NHL, and college sports.

    Extends ZoeaTool to support direct artifact creation for markdown tables.

    Example:
        tool = SportsNewsTool()
        # Get today's NBA games
        result = tool.forward(sport="nba", query_type="today")
        # Get NBA standings
        result = tool.forward(sport="nba", query_type="standings")
    """

    name = "sports_news"
    description = (
        "Get current sports scores, schedules, and standings from PlainTextSports.com. "
        "Use this tool to find out what games are playing today, current scores, "
        "standings, and schedules for NBA, NFL, NHL, and college sports. "
        "For 'today' queries, returns live scores and today's matchups. "
        "For 'standings' queries, returns current league standings. "
        "For 'schedule' queries, returns upcoming games."
    )
    inputs = {
        "sport": {
            "type": "string",
            "description": (
                "The sport/league to query. Options: 'nba', 'nfl', 'nhl', "
                "'ncaaf' (college football), 'ncaam' (men's college basketball), "
                "'ncaaw' (women's college basketball), 'premier-league', 'champions-league'"
            ),
        },
        "query_type": {
            "type": "string",
            "description": (
                "Type of information to retrieve. Options: "
                "'today' (today's games and scores - default), "
                "'standings' (current standings), "
                "'schedule' (upcoming schedule)"
            ),
            "nullable": True,
        },
    }
    output_type = "string"

    # Map sports to their URL paths and season formats
    SPORT_CONFIG = {
        "nba": {"path": "nba", "season": "2024-2025"},
        "nfl": {"path": "nfl", "season": "2024-2025"},
        "nhl": {"path": "nhl", "season": "2024-2025"},
        "ncaaf": {"path": "ncaaf", "season": "2024"},
        "ncaam": {"path": "ncaam", "season": "2024-2025"},
        "ncaaw": {"path": "ncaaw", "season": "2024-2025"},
        "premier-league": {"path": "premier-league", "season": "2024-2025"},
        "champions-league": {"path": "champions-league", "season": "2024-2025"},
    }

    def __init__(self, timeout: int = 15, **kwargs):
        """
        Initialize the SportsNewsTool.

        Args:
            timeout: Request timeout in seconds (default 15)
            **kwargs: Passed to ZoeaTool (including output_collection)
        """
        super().__init__(**kwargs)
        self.timeout = timeout
        self.base_url = "https://plaintextsports.com"
        self.user_agent = "Mozilla/5.0 (compatible; ZoeaStudioBot/1.0; +https://zoea.studio)"

    def _parse_games_to_markdown(self, html: str, sport: str) -> str | None:
        """
        Parse HTML from PlainTextSports.com and format as markdown table.

        PlainTextSports.com uses ASCII box art for game cards like:
        +--------------+
        |  7:00 PM ET  |
        | ATL 15-12    |
        | CHA 8-18     |
        +--------------+

        Args:
            html: Raw HTML from the site
            sport: Sport type for context

        Returns:
            Formatted markdown string or None if parsing fails
        """
        import re

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.debug("BeautifulSoup not available for HTML parsing")
            return None

        # Team abbreviation mapping for display names
        team_names = {
            # NBA
            "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
            "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
            "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
            "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
            "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
            "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
            "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
            "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
            "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
            "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
            # NFL
            "ARI": "Arizona Cardinals", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
            "CAR": "Carolina Panthers", "CIN": "Cincinnati Bengals", "GB": "Green Bay Packers",
            "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs", "LV": "Las Vegas Raiders",
            "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
            "NYJ": "New York Jets", "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
            "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans",
        }

        try:
            soup = BeautifulSoup(html, "html.parser")
            games = []

            # Find all game links (they contain the ASCII box art)
            game_links = soup.find_all("a", href=re.compile(r"/" + sport + r"/\d{4}-\d{2}-\d{2}/"))

            for link in game_links:
                text = link.get_text()
                lines = [l.strip().strip("|").strip() for l in text.split("\n") if l.strip()]

                # Skip if it's just box borders
                lines = [l for l in lines if not l.startswith("+") and not l.startswith("-")]

                if len(lines) >= 3:
                    # Format: [time, team1 record, team2 record]
                    time_str = lines[0].strip()
                    team1_line = lines[1].strip()
                    team2_line = lines[2].strip()

                    # Parse team lines: "ATL 15-12" or "ATL 105" (score)
                    team1_match = re.match(r"([A-Z]{2,3})\s+(.+)", team1_line)
                    team2_match = re.match(r"([A-Z]{2,3})\s+(.+)", team2_line)

                    if team1_match and team2_match:
                        abbr1, info1 = team1_match.groups()
                        abbr2, info2 = team2_match.groups()

                        name1 = team_names.get(abbr1, abbr1)
                        name2 = team_names.get(abbr2, abbr2)

                        # Determine if it's a score (number) or record (X-Y)
                        is_score = re.match(r"^\d+$", info1.strip())

                        games.append({
                            "time": time_str,
                            "away_team": name1,
                            "away_info": info1.strip(),
                            "home_team": name2,
                            "home_info": info2.strip(),
                            "is_score": bool(is_score),
                        })

            if not games:
                return None

            # Format as markdown tables
            output_lines = []

            # Separate scheduled vs in-progress/completed
            scheduled = [g for g in games if not g["is_score"]]
            with_scores = [g for g in games if g["is_score"]]

            if scheduled:
                output_lines.append("### Scheduled Games\n")
                output_lines.append("| Away | Home | Time |")
                output_lines.append("|------|------|------|")
                for g in scheduled:
                    output_lines.append(
                        f"| {g['away_team']} ({g['away_info']}) | "
                        f"{g['home_team']} ({g['home_info']}) | {g['time']} |"
                    )
                output_lines.append("")

            if with_scores:
                output_lines.append("### Scores\n")
                output_lines.append("| Away | Home | Status |")
                output_lines.append("|------|------|--------|")
                for g in with_scores:
                    output_lines.append(
                        f"| {g['away_team']} {g['away_info']} | "
                        f"{g['home_team']} {g['home_info']} | {g['time']} |"
                    )
                output_lines.append("")

            if not output_lines:
                return None

            return "\n".join(output_lines)

        except Exception as e:
            logger.debug(f"Failed to parse games HTML: {e}")
            return None

    def _build_url(self, sport: str, query_type: str) -> str:
        """Build the URL for the sports query."""
        config = self.SPORT_CONFIG.get(sport.lower())
        if not config:
            return ""

        path = config["path"]
        season = config["season"]

        if query_type == "today":
            # Today's games/scores - use bare path for current scoreboard
            # PlainTextSports.com shows today's games at /{sport}/ without date
            return f"{self.base_url}/{path}/"
        elif query_type == "standings":
            return f"{self.base_url}/{path}/{season}/standings"
        elif query_type == "schedule":
            return f"{self.base_url}/{path}/{season}/schedule"
        else:
            # Default to today
            return f"{self.base_url}/{path}/"

    @with_telemetry
    def forward(self, sport: str, query_type: str = "today") -> str:
        """
        Fetch sports data from PlainTextSports.com.

        Args:
            sport: The sport/league to query (nba, nfl, nhl, etc.)
            query_type: Type of query (today, standings, schedule)

        Returns:
            Plain text sports data or error message
        """
        # Validate sport
        sport_lower = sport.lower()
        if sport_lower not in self.SPORT_CONFIG:
            available = ", ".join(self.SPORT_CONFIG.keys())
            return f"Error: Unknown sport '{sport}'. Available options: {available}"

        # Validate query type
        valid_types = ["today", "standings", "schedule"]
        query_lower = query_type.lower()
        if query_lower not in valid_types:
            return f"Error: Unknown query_type '{query_type}'. Options: {', '.join(valid_types)}"

        # Build URL
        url = self._build_url(sport_lower, query_lower)
        if not url:
            return f"Error: Could not build URL for {sport}/{query_type}"

        try:
            import requests
            from markdownify import markdownify
        except ImportError as e:
            logger.error(f"Missing dependencies for SportsNewsTool: {e}")
            return "Error: Missing required packages. Please install 'requests' and 'markdownify'."

        try:
            headers = {"User-Agent": self.user_agent}
            response = requests.get(url, timeout=self.timeout, headers=headers)
            response.raise_for_status()

            # Try to parse structured game data for "today" queries
            if query_lower == "today":
                formatted = self._parse_games_to_markdown(response.text, sport_lower)
                if formatted:
                    today_date = timezone.localtime().strftime("%B %d, %Y")
                    header = f"## {sport.upper()} Games - {today_date}\n"
                    header += f"*Data from PlainTextSports.com*\n\n"
                    result = header + formatted
                    logger.debug(f"SportsNewsTool parsed {url}: {len(result)} chars")

                    # Create markdown artifact for the table
                    content_hash = hash(formatted) & 0xFFFFFF
                    self.create_artifact(
                        type="markdown",
                        path=f"_inline_table_{content_hash:06x}",
                        mime_type="text/markdown",
                        title=f"{sport.upper()} Games - {today_date}",
                        content=result,
                    )

                    return result

            # Fallback: Convert to markdown for cleaner output
            content = markdownify(response.text)

            # Clean up excessive whitespace
            import re

            content = re.sub(r"\n{3,}", "\n\n", content)
            content = re.sub(r"[ \t]+\n", "\n", content)
            content = content.strip()

            # Add context header
            today = timezone.localtime().strftime("%B %d, %Y")
            header = f"## {sport.upper()} - {query_type.title()}\n"
            header += f"*Data from PlainTextSports.com as of {today}*\n\n"

            result = header + content

            # Truncate if too long
            max_length = 8000
            if len(result) > max_length:
                result = result[:max_length] + "\n\n... (truncated)"

            logger.debug(f"SportsNewsTool fetched {url}: {len(result)} chars")
            return result

        except requests.exceptions.Timeout:
            logger.warning(f"SportsNewsTool timeout for {url}")
            return f"Error: Request timed out. PlainTextSports.com may be slow."

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "unknown"
            logger.warning(f"SportsNewsTool HTTP {status} for {url}")
            if status == 404:
                return f"Error: No {query_type} data found for {sport}. The season may not have started yet."
            return f"Error: HTTP {status} from PlainTextSports.com"

        except Exception as e:
            logger.error(f"SportsNewsTool error for {url}: {e}")
            return f"Error fetching sports data: {str(e)}"
