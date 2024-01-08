import asyncio
import json
from datetime import date as datelib
from datetime import timedelta
from typing import TypedDict

from dotenv import get_key
from fusion_stat import Fusion
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


async def get_coms_and_teams(
    fusion: Fusion,
    fusion_coms_params: list[FusionCompetitionParamsDict],
    pbar: tqdm,
) -> tuple[dict[str, CompetitionDict], dict[str, TeamDict]]:
    coms: dict[str, CompetitionDict] = {}
    teams: dict[str, TeamDict] = {}
    for params in fusion_coms_params:
        await asyncio.sleep(DELAY)

        fusion_com = await fusion.get_competition(**params)
        pbar.update(1)

        coms[fusion_com.info["id"]] = CompetitionDict(
            name=fusion_com.info["name"],
            logo=fusion_com.info["logo"],
        )

        for team in fusion_com.teams:
            teams[team["id"]] = TeamDict(
                name=team["name"],
                logo=team["logo"],
                shots=team["shooting"]["shots"],
                xg=team["shooting"]["xg"],
                score=None,
                played=team["played"],
            )

    return coms, teams


async def get_matches(
    fusion: Fusion,
    coms: dict[str, CompetitionDict],
    teams: dict[str, TeamDict],
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
                com = coms[fusion_match["competition"]["id"]]

                if fusion_match["score"]:
                    home_score, away_score = [
                        int(score)
                        for score in fusion_match["score"].split(" - ")
                    ]
                else:
                    home_score, away_score = None, None

                home = teams[fusion_match["home"]["id"]]
                away = teams[fusion_match["away"]["id"]]
                home["score"] = home_score
                away["score"] = away_score

                match = MatchDict(
                    name=fusion_match["name"],
                    utc_time=fusion_match["utc_time"],
                    finished=fusion_match["finished"],
                    competition=com,
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
            fusion_coms_params = await get_fusion_coms_params(fusion, pbar)
            coms, teams = await get_coms_and_teams(
                fusion, fusion_coms_params, pbar
            )
            matches = await get_matches(fusion, coms, teams, pbar)
    export(matches, "matches.json")


if __name__ == "__main__":
    asyncio.run(main())
