import asyncio
import json
from datetime import date as datelib
from datetime import timedelta
from typing import TypedDict

from dotenv import get_key
from fusion_stat import Fusion
from fusion_stat.models.competition import (
    InfoDict as FusionCompetitionInfoDict,
)
from fusion_stat.models.competition import (
    TeamDict as FusionCompetitionTeamDict,
)
from fusion_stat.models.competitions import (
    CompetitionParamsDict as FusionCompetitionParamsDict,
)
from httpx import AsyncClient
from tqdm import tqdm

TEST_HTTP_PROXY = get_key(".env", "TEST_HTTP_PROXY")
DELAY = 2


class CompetitionDict(TypedDict):
    name: str
    logo: str


class TeamDict(TypedDict):
    name: str
    logo: str
    shots: int
    xg: float
    score: int | None
    played: int


class MatchDict(TypedDict):
    name: str
    utc_time: str
    finished: bool
    competition: CompetitionDict
    home: TeamDict
    away: TeamDict


def generate_recent_dates() -> list[str]:
    today = datelib.today()
    dates = [
        (today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-1, 3)
    ]
    return dates


async def get_fusion_coms_params(
    fusion: Fusion,
    pbar: tqdm,
) -> list[FusionCompetitionParamsDict]:
    fusion_coms = await fusion.get_competitions()
    pbar.update(1)
    return fusion_coms.get_params()


async def get_fusion_coms_and_teams(
    fusion: Fusion,
    fusion_coms_params: list[FusionCompetitionParamsDict],
    pbar: tqdm,
) -> tuple[
    dict[str, FusionCompetitionInfoDict], dict[str, FusionCompetitionTeamDict]
]:
    fusion_coms: dict[str, FusionCompetitionInfoDict] = {}
    fusion_teams: dict[str, FusionCompetitionTeamDict] = {}
    for params in fusion_coms_params:
        await asyncio.sleep(DELAY)

        fusion_com = await fusion.get_competition(**params)
        pbar.update(1)

        fusion_coms[fusion_com.info["id"]] = fusion_com.info

        for team in fusion_com.teams:
            fusion_teams[team["id"]] = team

    return fusion_coms, fusion_teams


async def get_matches(
    fusion: Fusion,
    fusion_coms: dict[str, FusionCompetitionInfoDict],
    fusion_teams: dict[str, FusionCompetitionTeamDict],
    pbar: tqdm,
) -> dict[str, list[MatchDict]]:
    matches: dict[str, list[MatchDict]] = {}
    dates = generate_recent_dates()
    for date in dates:
        await asyncio.sleep(DELAY)

        fusion_matches = await fusion.get_matches(date=date)
        pbar.update(1)

        day_matches: list[MatchDict] = []
        if items := fusion_matches.items:
            for fusion_match in items:
                competition = CompetitionDict(
                    name=fusion_match["competition"]["name"],
                    logo=fusion_coms[fusion_match["competition"]["id"]]["logo"],
                )

                if fusion_match["score"]:
                    home_score, away_score = [
                        int(score)
                        for score in fusion_match["score"].split(" - ")
                    ]
                else:
                    home_score, away_score = None, None

                home_team = fusion_teams[fusion_match["home"]["id"]]
                home = TeamDict(
                    name=home_team["name"],
                    logo=home_team["logo"],
                    shots=int(home_team["shooting"]["shots"]),
                    xg=home_team["shooting"]["xg"],
                    score=home_score,
                    played=home_team["played"],
                )

                away_team = fusion_teams[fusion_match["away"]["id"]]
                away = TeamDict(
                    name=away_team["name"],
                    logo=away_team["logo"],
                    shots=int(away_team["shooting"]["shots"]),
                    xg=away_team["shooting"]["xg"],
                    score=away_score,
                    played=away_team["played"],
                )

                match = MatchDict(
                    name=fusion_match["name"],
                    utc_time=fusion_match["utc_time"],
                    finished=fusion_match["finished"],
                    competition=competition,
                    home=home,
                    away=away,
                )
                day_matches.append(match)
        matches[date] = day_matches
    return matches


def export(data: dict[str, list[MatchDict]], file: str) -> None:
    with open(file, "w") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))


async def main() -> None:
    async with AsyncClient(proxies=TEST_HTTP_PROXY) as client:
        fusion = Fusion(client=client)
        with tqdm(total=10) as pbar:
            coms_params = await get_fusion_coms_params(fusion, pbar)
            coms, teams = await get_fusion_coms_and_teams(
                fusion, coms_params, pbar
            )
            matches = await get_matches(fusion, coms, teams, pbar)
    export(matches, "matches.json")


if __name__ == "__main__":
    asyncio.run(main())
